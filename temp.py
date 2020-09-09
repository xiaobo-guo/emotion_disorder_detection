import json
import os
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime

data_type_list = ['anxiety', 'background', 'bipolar', 'depression']

source_data_folder = './data_back/reddit'
target_data_folder = './data/reddit'
user_folder = './data/user_list'

start_time = datetime.strptime("2018-09", "%Y-%m")
end_time = datetime.strptime("2020-04", "%Y-%m")

# gap_number = (end_time.year - start_time.year) * 12 + end_time.month - start_time.month + 1

# data = dict()

for data_type in data_type_list:
    # data[data_type] = [0 for _ in range(gap_number)]
    user_list = list()
    user_file = os.path.join(user_folder, data_type + '_user_list_back')
    source_data_file = os.path.join(source_data_folder, data_type)
    target_data_file = os.path.join(target_data_folder, data_type)
    if not os.path.exists(target_data_file):
        os.makedirs(target_data_file)

    with open(user_file, mode='r', encoding='utf8') as fp:
        for line in fp.readlines():
            user = line.split(' [info] ')[0]
            user_list.append(user)
    
    if data_type != 'background':
        suffix = '.before'
    else:
        suffix = ''

    for index, user in enumerate(user_list):
        data = list()
        source_user_data = os.path.join(source_data_file, user + suffix)
        target_user_data = os.path.join(target_data_file, user + suffix)
        with open(source_user_data, mode='r', encoding='utf8') as fp: 
            for line in fp.readlines():
                temp = json.loads(line.strip())
                for _, value in temp.items():
                    local_time = datetime.fromtimestamp((int(value['time'])))
                    local_time = datetime.strftime(local_time,"%Y-%m")
                    local_time = datetime.strptime(local_time, "%Y-%m")
                    if local_time > end_time and local_time < start_time:
                        continue
                    else:
                        data.append(temp)
        with open(target_user_data, mode='w', encoding='utf8') as fp:
            for item in data:
                fp.write(json.dumps(item)+'\n')
                    # gap = (local_time.year - start_time.year) * 12 + local_time.month - start_time.month
                    # if gap >= 0 and gap < 36:
                    #     data[data_type][gap] += 1



# for key, value in data.items():
#     # value = np.array(value)
#     # value = value / np.sum(value)
#     plt.plot(value, label=key)
# plt.legend()
# plt.show()
print('test')
                    


            