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
    
    attrs = ['x6', 'x5', 'x2', 'x1']

    coeffs = []

    for attr in attrs:
        value = getattr(params, attr)
        if np.isnan(value):
            coeffs.append(0.0)
        else:
            coeffs.append(float(value))
    
    return coeffs
        

## Processing #################################################################

# Workspace
ws = r'C:\Users\admin_jlehtoma\workspace\ForestIndexer\forestindexer\data'

# Feature data
feature = 'TestiData.gdb\TestiAineisto'
ds = os.path.join(ws, feature)
index_field_name = "INDEX"
fields = ['J_IKAKOK', 'TILAVUUS_HA', 'KEY', index_field_name]

# Parameters
parameters_file = "parameters.csv"
parameters = os.path.join(ws, parameters_file)
parameters = read_csv(parameters, sep=";")

if arcpy.Exists(ds):

    # Describe a feature class
    #
    desc = arcpy.Describe(ds)
    
    if index_field_name not in [field.name for field in desc.fields]:
        print("Creating index field: %s" % index_field_name)
        # Check if index field is present
        arcpy.AddField_management(ds, index_field_name, "FLOAT", 9, "", "", "", 
                                  "NULLABLE")

    # Create update cursor for feature class
    with arcpy.da.UpdateCursor(ds, fields) as cursor:
        
        # Keys are defined as PUULAJI_KASVULK_ALUE
        # Iterate over rows
        for row in cursor:
            # Extract the key for this row
            row_key = row[2]
            # Match a suitable row in the parameters DataFrame with the 
            # current key
            row_parameters = parameters[parameters['key'] == row_key]
            
            # Check that there is a mathing row in parameters DataFrame
            if not row_parameters.empty:
                print('Row key: %s' % row_key)
                print('Untransformed value: %s' % row[0])
                # Construct a list of cofficients for the polynomial
                coeffs = construct_coeffs(row_parameters)
                # Calculate the polynomial index
                index = polynomial_index(coeffs, row[0])
                print('Index value: %s' % index)
                row[3] = index
                cursor.updateRow(row)
                
else:
    print('Target feature class <{0}> does not exist'.format(ds))