import os

import arcpy
import numpy as np
from pandas import core, read_csv

## Helper functions ###########################################################

def polynomial_index(terms, value):
    '''Calculates an index transformation of value based on Nth degree (max 6) polynomial. The terms of the polynomial
    are provided as a list where the order of the element specifies the degree of the term and the value defined the
    coefficient of the term. Last item is the constant term.

    For example, terms = [2.5, 0.1, 1.4, 3] would be
    
    2.5x^3 + 0.1x^2 + 1.4x + 3
    
    and  terms = [2.5, 0, 0.1, 0, 1.4, 0] would be
    
    2.5x^5 + 0.1x^3 + 1.4x
    
    @param terms: list holding the terms
    @param value: numerical value to be transformed  
    
    '''
    
    poly = np.poly1d(terms)
    return poly(value)

def construct_terms(params):

    # Define the polynomial terms here (default behaviour is to go up to sixth term)
    # TODO: maximum value of term degrees is now hard coded, this should be constructed from the data provided

    attrs = ['x6', 'x5', 'x4', 'x3', 'x2', 'x', 'constant']

    coeffs = []

    for attr in attrs:
        value = getattr(params, attr)
        try:
            value = float(value)
            if np.isnan(value):
                coeffs.append(0.0)
            else:
                coeffs.append(value)
        except TypeError, e:
            arcpy.AddError("Could not handle value: {0}\n".format(value))
            arcpy.AddError(e)
            raise
    
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
        # Double keys are not ok, but will be tolerated. Use only the first row.
        if len(row_parameters) > 1:
            arcpy.AddWarning("More than entries ({0}) detected for the same key {1}".format(len(row_parameters),
                                                                                            row_key))
            arcpy.AddWarning("Using only the first row, fix this asap!")
            row_parameters = row_parameters.take([0])

        # Check that there is a matching row in parameters DataFrame
        if row_parameters.empty:
            arcpy.AddWarning("No parameter values found for key: {0}".format(row_key))
            no_params_rows += 1
        else:
            # Construct a list of coefficients for the polynomial
            try:
                terms = construct_terms(row_parameters)
            except TypeError:
                arcpy.AddWarning("Error encountered at row: {0}".format(row_parameters  ))
                continue
            # Calculate the polynomial index
            if row[0] is not None:
                poly_value = polynomial_index(terms, row[0])
            else:
                arcpy.AddWarning("Transformed field value Null for row key: {0}".format(row_key))
                continue

            # Constrict the poly value between 0 and 1
            if poly_value < 0:
                poly_value = 0
            elif poly_value > 1:
                poly_value = 1

            # Multiply the transformed value (polynomial index) with the value of the multiplier field
            if row[1] is not None:
                index = poly_value * row[1]
            else:
                arcpy.AddWarning("Multiplier field value Null for row key: {0}".format(row_key))
                continue

            if debug:
                arcpy.AddMessage("Row key: {0}".format(row_key))
                arcpy.AddMessage("Untransformed value: {0}".format(row[0]))
                arcpy.AddMessage("Transformed value: {0}".format(poly_value))
                arcpy.AddMessage("Multiplier value: {0}".format(row[1]))
                arcpy.AddMessage("Index value: {0}".format(index))

            row[3] = index
            cursor.updateRow(row)
            rows += 1

    arcpy.AddMessage("\n**** Finished ****")
    arcpy.AddMessage("Updated {0} rows".format(rows))
    if no_params_rows > 0:
        arcpy.AddWarning("Could not find parameters for {0} rows".format(no_params_rows))
