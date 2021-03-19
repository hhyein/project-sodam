from __future__ import print_function
import time
import json
import boto3
import os.path
import requests
from pydub import AudioSegment
from pydub.utils import mediainfo

# 파일 결합하기
'''
sound1 = AudioSegment.from_wav("filename01.wav")
sound2 = AudioSegment.from_wav("filename02.wav")
combined_sounds = sound1 + sound2
combined_sounds.export("joinedFile.wav", format = "wav")
'''

# 로컬 파일 전처리하기
local_file = "main.wav"
local_file_name = local_file.split(".")[0]
change_file = local_file_name + ".wav"

sound = AudioSegment.from_file(local_file)

if sound.frame_rate != 16000:
    sound = sound.set_frame_rate(16000)

if '.wav' not in local_file:
    sound.export(change_file, format = "wav")
    local_file = change_file

# 로컬 파일 버킷에 업로드하기
s3 = boto3.client('s3')
bucket_file = local_file
bucket_name = 'speech.to.text'

s3.upload_file(local_file, bucket_name, bucket_file)

# 버킷 파일 로컬에 저장하기
s3.download_file(bucket_name, bucket_file, local_file)

### 버킷 파일 텍스트화 하기
transcribe = boto3.client('transcribe')
job_name = bucket_file
job_uri = 's3://speech.to.text/' + job_name

transcribe.start_transcription_job(
    TranscriptionJobName = job_name,
    Media = {'MediaFileUri': job_uri},
    MediaFormat = 'wav',
    LanguageCode = 'ko-KR',
    Settings = {'ShowSpeakerLabels': True, 'MaxSpeakerLabels': 4}
)

while True:
    status = transcribe.get_transcription_job(TranscriptionJobName = job_name)
    if status['TranscriptionJob']['TranscriptionJobStatus'] in ['COMPLETED', 'FAILED']:
        break
    print("Not ready yet...")
    time.sleep(10)

### 텍스트화 파일 로컬에 저장하기
url = status['TranscriptionJob']['Transcript']['TranscriptFileUri']
r = requests.get(url, allow_redirects = True)
open('origin.json', 'wb').write(r.content)

with open("origin.json", "r", encoding = "utf-8") as json_file:
  json_data = json.load(json_file)

# start_time, speaker_label, end_time
result = []

for i in range(0, len(json_data['results']['speaker_labels']['segments'])):
  segments = json_data['results']['speaker_labels']['segments'][i]
  del segments['items']

  result.append(segments)

# 단어 단위를 문장 단위로 변경하기
count = 0
content = ""

for i in range(0, len(json_data['results']['items'])):
  # content = word
  try:
    if float(result[count]['end_time']) >= float(json_data['results']['items'][i]['end_time']):
      content += json_data['results']['items'][i]['alternatives'][0]['content'] + " "
      if i == len(json_data['results']['items']) - 1:
        result[count]['result'] = content 
      
    else:
      result[count]['result'] = content
      count += 1
      content = json_data['results']['items'][i]['alternatives'][0]['content'] + " "

  # content != word
  except:
    if i == len(json_data['results']['items']) - 1:
      result[count]['result'] = content
      
# list to dict
final_result = {}
final_result["result"] = result
final_result["speakers"] = json_data['results']['speaker_labels']['speakers']

with open('data.json', 'w', encoding = "utf-8") as json_file:
  json.dump(final_result, json_file, indent = 4)