import os

import arcpy
import numpy as np
from pandas import core, read_csv

## Helper functions ###########################################################

def polynomial_index(coeffs, value):
    '''Calculates an index transformation of value based on Nth level 
    polynomial. The level and coefficients of the polynomial are provided as
    a list where each element specifies the level and the coefficient. For
    example, coeffs = [2.5, 0.1, 1.4] would be
    
    2.5x^3 + 0.1x^2 + 1.4x
    
    and  coeffs = [2.5, 0, 0.1, 0, 1.4] would be
    
    2.5x^5 + 0.1x^3 + 1.4x
    
    @param coeffs: list holding the coefficients
    @param value: numerical value to be transformed  
    
    '''
    
    poly = np.poly1d(coeffs) 
    return poly(value)

def construct_coeffs(params):

    # Define the polynomial levels here (default behaviour is to go up to the sixth level)
    attrs = ['x6', 'x5', 'x4', 'x3', 'x2', 'x1']

    coeffs = []

    for attr in attrs:
        value = getattr(params, attr)
        if np.isnan(value):
            coeffs.append(0.0)
        else:
            coeffs.append(float(value))
    
    return coeffs
        

## Processing #################################################################

# Read in the parameters
feature = arcpy.GetParameterAsText(0)
transformed_field = arcpy.GetParameterAsText(1)
multiplied_field = arcpy.GetParameterAsText(2)
key_table_field = arcpy.GetParameterAsText(3)
index_field = arcpy.GetParameterAsText(4)
parameters_file = arcpy.GetParameterAsText(5)
key_parameters_field = arcpy.GetParameterAsText(6)
debug = arcpy.GetParameter(7)

fields = [transformed_field, multiplied_field, key_table_field, index_field]

# Try to read in the parameters
if os.path.exists(parameters_file):
    parameters = read_csv(parameters_file, sep=";")
else:
    arcpy.AddError("{0} does not exist.".format(parameters_file))
    raise arcpy.ExecuteError

# Describe a feature class
desc = arcpy.Describe(feature)

if index_field not in [field.name for field in desc.fields]:
    arcpy.AddMessage("Creating index field: {0}".format(index_field))
    # Check if index field is present
    arcpy.AddField_management(feature, index_field, "FLOAT", 9, "", "", "", "NULLABLE")
else:
    arcpy.AddMessage("Updating existing index field")

# Create update cursor for feature class. Note that only a set of fields in a particular order are used. These fields
# are defined by the user.
with arcpy.da.UpdateCursor(feature, fields) as cursor:

    rows = 0
    no_params_rows = 0

    # Iterate over rows
    for row in cursor:
        # Extract the key for this row
        row_key = row[2]
        # Match a suitable row in the parameters DataFrame with the current key
        row_parameters = parameters[parameters[key_parameters_field] == row_key]

        # Check that there is a matching row in parameters DataFrame
        if row_parameters.empty:
            arcpy.AddWarning("No parameter values found for key: {0}".format(row_key))
            no_params_rows += 1
        else:
            # Construct a list of coefficients for the polynomial
            coeffs = construct_coeffs(row_parameters)
            # Calculate the polynomial index
            poly = polynomial_index(coeffs, row[0])
            # Multiply the transformed value (polynomial index) with the value of the multiplier field
            index = poly * row[1]

            if debug:
                arcpy.AddMessage("Row key: {0}".format(row_key))
                arcpy.AddMessage("Untransformed value: {0}".format(row[0]))
                arcpy.AddMessage("Transformed value: {0}".format(poly))
                arcpy.AddMessage("Multiplier value: {0}".format(row[1]))
                arcpy.AddMessage("Index value: {0}".format(index))

            row[3] = index
            cursor.updateRow(row)
            rows += 1

    arcpy.AddMessage("\n**** Finished ****")
    arcpy.AddMessage("Updated {0} rows".format(rows))
    if no_params_rows > 0:
        arcpy.AddWarning("Could not find parameters for {0} rows".format(no_params_rows))
