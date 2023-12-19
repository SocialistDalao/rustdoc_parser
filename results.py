import os


MIN_VERSION = 1
MAX_VERSION = 63
total_unstable_collected = 0
total_unstable_exist = 0
for i in range(MIN_VERSION, MAX_VERSION+1):
    cmd = 'cat tmp.txt | grep "'+ '1\.' + str(i) + '\.0 ' + '";'
    result = os.popen(cmd).read()
    result_list = result.split(' ')
    if len(result_list) != 3:
        continue
    unstable_collected = int(result_list[1])
    unstable_exist = int(result_list[2])
    total_unstable_collected += unstable_collected
    total_unstable_exist += unstable_exist
    coverage = unstable_collected / unstable_exist
    print(result_list[0], unstable_collected, unstable_exist, format(coverage, '.2%'))
print('Total', total_unstable_collected, total_unstable_exist, format(total_unstable_collected / total_unstable_exist, '.2%'))