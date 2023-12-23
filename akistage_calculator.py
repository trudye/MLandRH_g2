# -*- coding: utf-8 -*-
"""AKIstage calculator.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1T8eK8UBFaCFsYLesrNyRYBqKXQoOhe5v
"""

# sets *your* project id
PROJECT_ID = "lateral-avatar-405811" #@param {type:"string"}

# Commented out IPython magic to ensure Python compatibility.
# %matplotlib inline
!pip install amsterdamumcdb
import amsterdamumcdb
import psycopg2
import pandas as pd
import numpy as np
import re

import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib as mpl

import io
from IPython.display import display, HTML, Markdown

# sets default dataset for AmsterdamUMCdb
DATASET_PROJECT_ID = 'amsterdamumcdb' #@param {type:"string"}
DATASET_ID = 'version1_0_2' #@param {type:"string"}
LOCATION = 'eu' #@param {type:"string"}

import os
from google.colab import auth

# all libraries check this environment variable, so set it:
os.environ["GOOGLE_CLOUD_PROJECT"] = PROJECT_ID

auth.authenticate_user()
print('Authenticated')

# Commented out IPython magic to ensure Python compatibility.
# %load_ext google.colab.data_table
from google.colab.data_table import DataTable

# change default limits:
DataTable.max_columns = 50
DataTable.max_rows = 30000

from google.cloud.bigquery import magics
from google.cloud import bigquery

# sets the default query job configuration
def_config = bigquery.job.QueryJobConfig(default_dataset=DATASET_PROJECT_ID + "." + DATASET_ID)
magics.context.default_query_job_config = def_config

# Commented out IPython magic to ensure Python compatibility.
# %%bigquery admissions
# SELECT * FROM admissions





#open dataframe
#import pandas as pd
#df_AKI = pd.read_csv("sample_data/Merged_v1.csv")

import pandas as pd

config_gbq = {'query':
          {'defaultDataset': {
              "datasetId": DATASET_ID,
              "projectId": DATASET_PROJECT_ID
              },
           'Location': LOCATION}
           }

creat = pd.read_gbq(
    '''
    SELECT
        admissionid
        , itemid
        , value
        , unitid
        , measuredat
        , registeredby
    FROM numericitems
    WHERE itemid IN (
        6836  --Kreatinine
        , 9941  --Kreatinine (bloed)
        , 14216  --KREAT enzym. (bloed)
    )
    '''
    , configuration=config_gbq, use_bqstorage_api=True)

#show number of records in the dataframe
print(f'Number of creatinine values: {len(creat)}')

#show first 1000 items
creat.head(1000)

urine_output = pd.read_gbq(
    '''
    SELECT
        admissionid
        , itemid
        , value
        , unitid
        , measuredat
        , registeredby
        , measuredat/(1000*60*60) --hours
          AS measuredat_hours
    FROM numericitems
    WHERE itemid IN (
        8794  --UrineCAD
        , 8796  --UrineSupraPubis
        , 8798 --UrineSpontaan
        , 8800 --UrineIncontinentie
        , 8803 --UrineUP
        , 10743 --Nefrodrain li Uit
        , 10745 --Nefrodrain re Uit
        , 19921 --UrineSplint Li
        , 19922 --UrineSplint Re
    )
    '''
    , configuration=config_gbq, use_bqstorage_api=True)
#show number of records in the dataframe
print(f'Number of urine output values: {len(urine_output)}')

#show first 1000 items
urine_output.head(1000)

dict_avgweight = {'70-79':75, '60-69':65, '80-89':85,
                  '59-': 55, '90-99': 95, '110+': 115, '100-109':105,
                  ' ': ' '}

def get_weight(admission_id):
  patient_data =admissions[admissions['admissionid'] == admission_id].iloc[0]
  #print(patient_data['weightgroup'])
  #print(str(weight_group['weightgroup']))
  if patient_data['weightgroup'] == None:
    return 80
  else:
    weight_group = patient_data
    return dict_avgweight[weight_group['weightgroup']]

def sum_urine_output(data, time):
  max_total_urine_output = 0
  for index, row in data.iterrows():
    #hour_value = row['value']

    current_time = row['measuredat_hours']
    data_within_time=data[(data['measuredat_hours'] - current_time) < time]

    weight = get_weight(row['admissionid'])
    #print(data_within_time)
    total_urine_output = (sum(data_within_time['value']) / weight) / time
    #print(total_urine_output)

    if total_urine_output > max_total_urine_output:
      max_total_urine_output = total_urine_output

    #final_row = data_within_time.iloc[-1:]['measuredat_hours']

    #if final_row == data.iloc[-1:]['measuredat_hours']:
    return max_total_urine_output
    #  break

from math import nan
#AKI with creatinin + urine output
df_AKI_stage = pd.DataFrame(columns=['admissionid', 'AKI_stage'])
for adm in creat['admissionid'].unique():
  #print(adm)
  data_creat = creat[creat['admissionid'] == adm] #can be selected for a limited amt. of time
  baseline_creat = data_creat.iloc[0]['value'] #maybe change to value with earliest date?
  max_creat = data_creat['value'].max()
  increase_creat = max_creat/baseline_creat

  data_urineoutput = urine_output[urine_output['admissionid'] == adm]
    #urine_output = sum_urine_output(data_urineoutput,)
  #print(sum_urine_output(data_urineoutput,24))

  if sum_urine_output(data_urineoutput,24) == None:
    urineoutput_stage3 = 0.5
  else: urineoutput_stage3 = sum_urine_output(data_urineoutput,24)

  if sum_urine_output(data_urineoutput,12) == None:
    urineoutput_stage2 = 0.5
  else: urineoutput_stage2 = sum_urine_output(data_urineoutput,12)

  if sum_urine_output(data_urineoutput,6) == None:
    urineoutput_stage1 = 0.5
  else: urineoutput_stage1 = sum_urine_output(data_urineoutput,6)


  if (increase_creat > 2.9) or (urineoutput_stage3 < 0.3):
    df_AKI_stage.append({"admissionid":adm, "AKI_stage":3},ignore_index=True)
  elif ((1.9 < increase_creat <= 2.9) or (urineoutput_stage2 < 0.5)):
    df_AKI_stage.append({"admissionid":adm, "AKI_stage":2},ignore_index=True)
  elif (1.5 <= increase_creat <= 1.9) or urineoutput_stage1 < 0.5: #if time >= 12, then stage 2 will be selected
    df_AKI_stage.append({"admissionid":adm, "AKI_stage":1},ignore_index=True)
  elif increase_creat < 1.5 : #could be just "else?"
    df_AKI_stage.append({"admissionid":adm, "AKI_stage":0},ignore_index=True)

df_AKI_stage

df_AKI_stage.to_csv("df_AKI_stage.csv")