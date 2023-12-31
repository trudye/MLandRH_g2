# -*- coding: utf-8 -*-
"""data_selection.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/15penttI5St-Xff1r8X1wZaumw9D_WGmu
"""

# Commented out IPython magic to ensure Python compatibility.
# sets *your* project id
PROJECT_ID = "lateral-avatar-405811" #@param {type:"string"}

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

import os
from google.colab import auth

# sets default dataset for AmsterdamUMCdb
DATASET_PROJECT_ID = 'amsterdamumcdb' #@param {type:"string"}
DATASET_ID = 'version1_0_2' #@param {type:"string"}
LOCATION = 'eu' #@param {type:"string"}



# all libraries check this environment variable, so set it:
os.environ["GOOGLE_CLOUD_PROJECT"] = PROJECT_ID

auth.authenticate_user()
print('Authenticated')


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

import pandas as pd

config_gbq = {'query':
          {'defaultDataset': {
              "datasetId": DATASET_ID,
              "projectId": DATASET_PROJECT_ID
              },
           'Location': LOCATION}
           }

ABP = pd.read_gbq(
    '''
    SELECT
        n.admissionid,
        n.itemid,
        n.item,
        n.value,
        CASE
            WHEN NOT registeredby IS NULL THEN TRUE
            ELSE FALSE
        END as validated,
        (measuredat - a.admittedat)/(1000*60) AS time
    FROM numericitems n
    LEFT JOIN admissions a ON
    n.admissionid = a.admissionid
    WHERE itemid IN (
        6642, --ABP gemiddeld
        6679, --Niet invasieve bloeddruk gemiddeld
        8843 --ABP gemiddeld II
    )
    AND (measuredat - a.admittedat) <= 1000*60*60*24 --measurements within 24 hours
    '''
, configuration=config_gbq, use_bqstorage_api=True)

ABP
# pd.Series(reason_for_diagnosis["admissionid"]).is_unique
# reason_for_diagnosis["admissionid"].unique()

ABP = ABP[ABP['item'] == "ABP gemiddeld"]

df_baseline_ABP = pd.DataFrame()


for admissionid in ABP['admissionid'].unique():
  data = ABP[ABP['admissionid'] == admissionid]
  if len(data) > 0:
    min_row = data[data['time'] == min(data['time'])]
    baseline_ABP = min_row['value'].item()
    df_baseline_ABP = df_baseline_ABP.append([[admissionid, baseline_ABP]])
  else: df_baseline_sepsis = df_baseline_sepsis.append([[admissionid, np.NAN]])

df_baseline_ABP.rename(columns = {0:'admissionid', 1: 'baseline_ABP'}, inplace = True)

sepsis = pd.read_gbq(
    '''
    SELECT
        admissionid,
        CASE valueid
            WHEN 1 THEN 1 --'Ja'
            WHEN 2 THEN 0 --'Nee'
        END as sepsis_at_admission,
        ROW_NUMBER() OVER(
            PARTITION BY
                admissionid
            ORDER BY
                updatedat DESC, --prefer sepsis diagnosis with most recent update time
                measuredat DESC) AS rownum --prefer sepsis diagnosis with most recent session/form time
    FROM listitems
    WHERE
        itemid = 15808
    '''
, configuration=config_gbq, use_bqstorage_api=True)
#sepsis_last_updated = sepsis[sepsis['rownum'] == 1] # this one needs to be put in somewhere
sepsis

data = sepsis.loc[sepsis['admissionid'] == 23530]
data = data.loc[data['rownum'] == 1]

data['sepsis_at_admission'].item()

df_baseline_sepsis = pd.DataFrame()

for admissionid in ABP['admissionid'].unique():
  data = sepsis[sepsis['admissionid'] == admissionid]
  if len(data) > 0:
    baseline_data = data[data['rownum'] == 1]
    print(str(baseline_data['sepsis_at_admission'])) # not pd.isna(q)
    #if type(baseline_data['sepsis_at_admission']) == 'NAType' :
    if pd.isna(baseline_data['sepsis_at_admission'].item()) :
      df_baseline_sepsis = df_baseline_sepsis.append([[admissionid, 0]])
    else:
      baseline_sepsis = int(baseline_data['sepsis_at_admission'])
      #print(baseline_sepsis)
      df_baseline_sepsis = df_baseline_sepsis.append([[admissionid, baseline_sepsis]])
  else: df_baseline_sepsis = df_baseline_sepsis.append([[admissionid, 0]])

df_baseline_sepsis.rename(columns = {0:'admissionid', 1: 'baseline_sepsis'}, inplace = True)



df_sepsis_inIC = pd.DataFrame() #sepsis = 1 after rownum=1

for admissionid in ABP['admissionid'].unique():
  data = sepsis[sepsis['admissionid'] == admissionid]
  if 1 in data['sepsis_at_admission']:
    df_sepsis_inIC = df_sepsis_inIC.append([[admissionid, 1]])
  else: df_sepsis_inIC = df_sepsis_inIC.append([[admissionid, 0]])

df_sepsis_inIC.rename(columns = {0:'admissionid', 1: 'sepsis_inIC'}, inplace = True)



df_sepsis = pd.merge(df_baseline_sepsis, df_sepsis_inIC, on='admissionid', how='outer')



blood_transfusion = pd.read_gbq(
    '''
    SELECT *
        --admissionid,
        --valueid,
        --CASE valueid
            --WHEN 1 THEN 1 --'Ja'
            --WHEN 2 THEN 0 --'Nee'
        --END as sepsis_at_admission,
       -- ROW_NUMBER() OVER(
         --   PARTITION BY
           --     admissionid
            --ORDER BY
              --  updatedat DESC, --prefer sepsis diagnosis with most recent update time
                --measuredat DESC) AS rownum --prefer sepsis diagnosis with most recent session/form time
    FROM listitems
    WHERE
        itemid = 8974
    '''
, configuration=config_gbq, use_bqstorage_api=True)

blood_transfusion

admissions['nefrology_patient'] = [1 if specialty == "Nefrologie" else 0 for specialty in admissions['specialty']]

#merging data

df_full = pd.merge(admissions, df_baseline_ABP, on='admissionid', how='outer')
df_full = pd.merge(df_full, df_sepsis, on='admissionid', how='outer')
#df_full = pd.concat([df_full, blood_transfusion], keys=['admissionid'])

df_full

df_final = df_full[['admissionid','urgency', 'gender', 'agegroup', 'weightgroup',  'heightgroup', 'specialty', 'baseline_ABP', 'baseline_sepsis',
                    'sepsis_inIC']]

df_final['sepsis_inIC']=df_final['sepsis_inIC'].fillna(0)
#df_final['sepsis_ic']=df_final['sepsis_ic'].fillna(0)



fill_value_for_abp=df_final['baseline_ABP'].mean()
df_final['baseline_ABP']=df_final['baseline_ABP'].fillna(int(fill_value_for_abp))

df_final['specialty'].unique()

#create one-hot encoded data:

df_final_encoded = pd.get_dummies(df_final, columns=['gender','heightgroup', 'weightgroup','agegroup'], dummy_na=False)

#gender = 0 for 'gender_Man', 'gender_Vrouw' if unknown:
df_final_encoded = df_final_encoded.drop(columns=['gender_'])

df_final_encoded.columns

#see AKIstage calculator for AKIstage file:
AKI_stage = pd.read_csv("/content/sample_data/AKI_stage_output.csv")

df_final_withAKIstage = pd.merge(df_final_encoded, AKI_stage, on='admissionid', how='outer')

df_final_withAKIstage.to_csv('df_final_withAKIstage.csv')

df_final_withAKIstage.iloc[:,26].head()

from sklearn.model_selection import train_test_split
X = df_final_withAKIstage.iloc[:, 1:26]
y = df_final_withAKIstage.iloc[:,26]
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.30, random_state=42)

X_train.to_csv('X_train.csv')
X_test.to_csv('X_test.csv')
y_train.to_csv('y_train.csv')
y_test.to_csv('y_test.csv')