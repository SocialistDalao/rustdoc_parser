import json
import re
import os
import sys
from glob import glob



def test_serial():
    # serialize Python object and write to JSON file
    # python_obj = {'name': 'John', 'age': 30}
    # with open('data.json', 'w') as file:
    #     json.dump(python_obj, file)
    with open('test_serial.json', 'r') as file:
        python_obj = json.load(file)
    print(python_obj['api'])  


def get_pure_string(string: str) -> str:
    '''
    Remove all special characters from a string.
    '''
    string = string.replace('⎘', u'')
    string = string.replace(u'\xa0', u' ')
    string = string.replace(u'=', u' = ')
    string = string.replace(u'= =', u'==')
    string = re.sub(' +',' ',string)
    if string[-2:] == ', ':
        string = string[0:-2]
    return string



def empty_stability():
    return {
        'ruf': '',
        'status': '',
        'since': '',
        'full': '',
    }

def empty_api():
    return {
        'submodule': '',
        'head': '',
        'impl': '',
        'api': '',
        'stability': list(),
        'next_api_index': -1, # Index of the same abi in next doc version in the same submodule. 
        'duration': 0, # Duration of the same abi (in versions)
    }

def empty_submodule():
    return {
        'kind': '',
        'path': '',
        'api': '',
        'stability': list(),
        'plain_apis': list(), # -> api list
    }


# Transfer original raw string into well formatted one.
def analyze_stability(stability: list) -> list:
    stability_list = list()
    for item in stability:
        item = get_pure_string(item)
        # print(item)
        # Unstable
        for matched_unstable in re.findall('🔬 This is a nightly-only experimental API\.\s+\(\w+\s#[0-9]+\)', item):
            # print('Unstable 1')
            unstable_part = re.search('\(\w+\s', matched_unstable)[0]
            ruf = unstable_part[1:-1]
            new_stability = empty_stability()
            new_stability['ruf'] = ruf
            new_stability['status'] = 'unstable'
            new_stability['full'] = matched_unstable
            stability_list.append(new_stability)
        # Unstable 2
        for matched_unstable in re.findall('🔬 This is a nightly-only experimental API\.\s\(\w+\)', item):
            # print('Unstable 2')
            unstable_part = re.search('\(\w+\)', matched_unstable)[0]
            ruf = unstable_part.split(' ')[0][1:-1]
            new_stability = empty_stability()
            new_stability['ruf'] = ruf
            new_stability['status'] = 'unstable'
            new_stability['full'] = matched_unstable
            stability_list.append(new_stability)
        # Unstable 3: Unstable (wait_timeout_with #27748): unsure if this API is broadly needed or what form it should take\n
        for matched_unstable in re.findall('Unstable \(\w+ #[0-9]+\)', item):
            # print('Unstable 3')
            unstable_part = re.search('\(\w+ #[0-9]+\)', matched_unstable)[0]
            ruf = unstable_part.split(' ')[0][1:]
            new_stability = empty_stability()
            new_stability['ruf'] = ruf
            new_stability['status'] = 'unstable'
            new_stability['full'] = matched_unstable
            stability_list.append(new_stability)
        # Unstable 4: Unstable (libc): use libc from crates.io\n
        for matched_unstable in re.findall('Unstable \(\w+\)', item):
            # print('Unstable 4')
            unstable_part = re.search('\(\w+\)', matched_unstable)[0]
            ruf = unstable_part.split(' ')[0][1:-1]
            new_stability = empty_stability()
            new_stability['ruf'] = ruf
            new_stability['status'] = 'unstable'
            new_stability['full'] = matched_unstable
            stability_list.append(new_stability)
        # Deprecated
        for matched_unstable in re.findall('Deprecated since 1.[0-9]+(?:.[0-9]+)*: .+\n', item):
            since = re.search('1.[0-9]+(?:.[0-9]+)*', matched_unstable)[0]
            new_stability = empty_stability()
            new_stability['status'] = 'deprecated'
            new_stability['since'] = since
            new_stability['full'] = matched_unstable
            stability_list.append(new_stability)
    if len(stability_list) != len(stability):
        if len(stability) != 1 or 'This is supported on' not in stability[0] == '':
            print('Unhandled Stability', stability)
    for stability_item in stability_list:
        if stability_item['status'] == 'unstable' and stability_item['ruf'] == '':
            print('Unhandled Stability', stability)
            break
    # if len(stability_list) != 0:
    #     print(stability_list)
    return stability_list


# Returns (sumodule_path, api_list)
def recover_info(submodule) -> (str, dict):
    """
    Recover the information of a submodule from analysis results.
    Return a list containing minimal APIs.
    We do extra operations to eliminate the redundancy of the results.
    1. Sometimes it includes `\u24d8` which is followed by notable-trait info, useless in our study.
    2. Stability includes portability, deprecate, unstable items. We only latter two.
    """
    plain_submodule = empty_submodule()
    api_list = list()
    submodule_path = get_pure_string(submodule['path'])
    # TODO: Now, we don't add submodule into the list.
    # api_list.append(submodule_api)
    for item in submodule['items']:
        head = item['head']
        # Implementators occur both in Trait and items implementing that trait. Remove duplicate counting.
        # As the implementation in the trait may not show complete, we remove duplicate one in trait rather than in items.
        if head == 'Implementors' and submodule['kind'] == 'Trait':
            continue
        if head == 'Blanket Implementations' and submodule['kind'] == 'Trait':
            print('Warning: Blanket Implementations', submodule_path)
        for impl in item['impls']:
            impl_name = impl['impl']
            for function in impl['functions']:
                api = function['api']
                # if 'impl' in api:
                    # print('Warning: impl in api', api)
                api = api.split('\u24d8')[0]
                api = api.replace('pub ', '') # All analyzed APIs are public, whether marked or not.
                api = api.replace('default ', '') # `Default` keyword does not affect API.
                stability = function['stability']
                api_info = empty_api()
                api_info['submodule'] = submodule_path
                api_info['head'] = head
                api_info['impl'] = get_pure_string(impl_name)
                api_info['api'] = get_pure_string(api)
                api_info['stability'] = analyze_stability(stability)
                api_list.append(api_info)
    plain_submodule['kind'] = submodule['kind']
    plain_submodule['path'] = submodule_path
    plain_submodule['api'] = get_pure_string(submodule['api'])
    plain_submodule['stability'] = analyze_stability(plain_submodule['stability'])
    plain_submodule['plain_apis'] = api_list
    return (submodule_path, plain_submodule)
    


def is_api_same(api1: dict, api2: dict) -> bool:
    return api1['impl'] == api2['impl'] and api1['api'] == api2['api']


# TODO: Now we assume different `impl` means different API. But slightly limited changed impl should be considered the same API.
def is_same_api(api1: dict, api2: dict) -> bool:
    '''
    Compare two APIs to see if they are the same, but different parameters are tolerated.
    '''
    if api1['impl'] != api2['impl']:
        return False
    if api1['api'] == api2['api']:
        return True
    function_name1 = re.search('fn \w+[<|(]', api1['api'])
    function_name2 = re.search('fn \w+[<|(]', api2['api'])
    if function_name1 and function_name2:
        if function_name1[0][3:-1] == function_name2[0][3:-1]:
            # print('API Changed', api1['submodule'])
            # print(api1)
            # print(api2)
            return True
    # if not function_name1 and api1['api'][0:6] == api2['api'][0:6]:
    #     print('Similar', api1['submodule'])
    #     print(api1['api'])
    #     print(api2['api'])
    return False


removed_API = []
new_API = []
def print_removed_api_info(current_version, api_list: list, new_api_list: list):
    '''
    Print removed API info.
    '''
    index_set = set()
    for api in api_list:
        next_api_index = api['next_api_index']
        if next_api_index == -1:
            # print('Removed API:', api)
            api['version'] = current_version
            removed_API.append(api)
        else:
            index_set.add(next_api_index)
    for idx, api in enumerate(new_api_list):
        if idx not in index_set:
            # print('New API:', api)
            api['version'] = current_version
            new_API.append(api)


def statistics_removed_api_info():
    removed_fn_count = 0
    removed_impl_count = 0
    removed_type_count = 0
    new_fn_count = 0
    new_impl_count = 0
    new_type_count = 0
    for api in removed_API:
        if 'fn ' in api['api']:
            removed_fn_count += 1
        elif len(api['api']) > len('impl') and api['api'][0:4] == 'impl':
            removed_impl_count += 1
            print('Removed API:', api)
        elif len(api['api']) > len('type ') and api['api'][0:5] == 'type ':
            removed_type_count += 1
    for api in new_API:
        if 'fn ' in api['api']:
            new_fn_count += 1
        elif len(api['api']) > len('impl') and api['api'][0:4] == 'impl':
            new_impl_count += 1
            print('New API:', api)
        elif len(api['api']) > len('type ') and api['api'][0:5] == 'type ':
            new_type_count += 1
    print('Removed API Count', len(removed_API), 'New API Count', len(new_API))
    print('Removed Function Count', removed_fn_count, 'New Function Count', new_fn_count)
    print('Removed Impl Count', removed_impl_count, 'New Impl Count', new_impl_count)
    print('Removed Type Count', removed_type_count, 'New Type Count', new_type_count)


def print_new_module_info(doc:dict, doc_new:dict):
    '''
    Print new module info.
    '''
    total_new_api_count = 0
    total_new_submodule_count = 0
    for (submodule_path, plain_submodule) in doc_new.items():
        api_list = plain_submodule['plain_apis']
        if submodule_path not in doc:
            total_new_api_count += len(api_list)
            total_new_submodule_count += 1
            # print('New Module:', submodule_path, len(api_list))
            # print(*api_list, sep='\n')
            # print('------------------')
    print('New Module Count', total_new_submodule_count, 'New API Count', total_new_api_count)


def classify_removed_api_info(doc:dict, doc_new:dict):
    '''
    Classify different types of removed APIs.
    Print removed count in each type.
    '''
    removed_count = {}
    new_count = {}
    for (submodule_path, plain_submodule) in doc.items():
        api_list = plain_submodule['plain_apis']
        index_set = set()
        for api in api_list:
            next_api_index = api['next_api_index']
            if next_api_index == -1:
                removed_count[api['head']] = removed_count.get(api['head'], 0) + 1
                # if api['head'] == 'Variants':
                print('Removed API:', api)
            else:
                index_set.add(next_api_index)

        if submodule_path in doc_new:
            new_api_list = doc_new[submodule_path]['plain_apis']
            for idx, api in enumerate(new_api_list):
                if idx not in index_set:
                    new_count[api['head']] = new_count.get(api['head'], 0) + 1
                    # if api['head'] == 'Variants':
                    print('New API:', api)
    
    print('Removed API Count', dict(sorted(removed_count.items(), key=lambda item: item[1], reverse=True)))
    print('New API Count (In old submodule)', dict(sorted(new_count.items(), key=lambda item: item[1], reverse=True)))


def count_truenew_api(doc:dict, doc_new:dict):
    '''
    Count the number of new API in doc_new, which are not in doc.
    We remove `Implementors` as they are passively implemented, determined by traits.
    Sometimes it cannot reflect true api changes.
    '''
    count = 0
    fake_count = 0
    for (submodule_path, plain_submodule) in doc.items():
        api_list = plain_submodule['plain_apis']
        latest_fake_count = fake_count
        if submodule_path not in doc_new:
            continue
        index_set = set()
        new_api_list = doc_new[submodule_path]['plain_apis']
        for api in api_list:
            next_api_index = api['next_api_index']
            index_set.add(next_api_index)
        for idx, api in enumerate(new_api_list):
            if idx not in index_set and api['head']:
                if plain_submodule['kind'] != 'Trait' or api['head'] not in ['Implementors', 'Blanket Implementations']:
                    count += 1
                else:
                    fake_count += 1
        if fake_count - latest_fake_count > 50:
            print('Submodule:', submodule_path)
            print('Fake New API', fake_count - latest_fake_count)
    for (submodule_path, plain_submodule) in doc_new.items():
        api_list = plain_submodule['plain_apis']
        if submodule_path not in doc:
            count += len(api_list)
    return count


def get_stability_count(api_list: list):
    unstable_api_count = 0
    for api in api_list:
        for stability in api['stability']:
            if stability['status'] == 'unstable':
                unstable_api_count += 1
                break
    return unstable_api_count


def is_api_deprecated(api: dict):
    for stability in api['stability']:
        if stability['status'] == 'deprecated':
            return True
    return False


def is_api_unstable(api: dict):
    for stability in api['stability']:
        if stability['status'] == 'unstable':
            return True
    return False


def is_ruf_same(api:dict, next_api:dict):
    for stability in api['stability']:
        if stability['status'] == 'unstable':
            for next_stability in next_api['stability']:
                if stability['ruf'] != '' and next_stability['ruf'] != '' and stability['ruf'] == next_stability['ruf']:
                    return True
    return False



def construct_api_binding(docs:dict, MIN_VERSION, MAX_VERSION):
    '''
    Connect the API evolution in different versions.
    '''
    results = {}
    remained_api_count = 0
    remained_unstable_api_count = 0
    last_api_count = 0
    last_same_count = 0
    last_modify_count = 0
    last_removed_count = 0
    last_trueremoved_count = 0
    last_truemodify_count = 0
    last_same_unstable_count = 0
    last_modify_unstable_count = 0
    last_removed_unstable_count = 0
    last_late_unstable_count = 0
    last_stabalized_count = 0
    last_change_ruf_count = 0
    for i in range(MIN_VERSION, MAX_VERSION+1):
        index = i - MIN_VERSION
        api_count = 0
        same_count = 0
        modify_count = 0
        removed_count = 0
        trueremoved_count = 0
        truemodify_count = 0
        unstable_api_count = 0
        same_unstable_count = 0
        modify_unstable_count = 0
        removed_unstable_count = 0
        late_unstable_count = 0
        stabalized_count = 0
        change_ruf_count = 0
        for (submodule_path, plain_submodule) in docs[index].items():
            api_list = plain_submodule['plain_apis']
            api_count += len(api_list)
            unstable_api_count += get_stability_count(api_list)
            if i == MAX_VERSION: 
                continue
            # Removed submodule
            if submodule_path not in docs[index+1]:
                # print('Removed Submodule:', submodule_path, len(api_list))
                removed_count += len(api_list)
                continue
            new_api_list = docs[index+1][submodule_path]['plain_apis']
            # for api in api_list:
                # for idx, new_api in enumerate(new_api_list):
                #     if is_same_api(api, new_api):
                #         if api['next_api_index'] != -1:
                #             # print('Error: next_api_index already set', api['submodule'], api['api'])
                #             break
                #         api['next_api_index'] = idx
                #         new_api['duration'] = api['duration'] + 1
            # analyze_api_evolution
            for api in api_list:
                unstable = is_api_unstable(api)
                if api['next_api_index'] != -1:
                    new_api = new_api_list[api['next_api_index']]
                    new_api['duration'] = api['duration'] + 1
                if api['next_api_index'] == -1:
                    removed_count += 1
                    if unstable:
                        removed_unstable_count += 1
                    # if api['head'] not in ['Implementors', 'Blanket Implementations']:
                    #     trueremoved_count += 1
                else:
                    next_api = docs[index+1][submodule_path]['plain_apis'][api['next_api_index']]
                    next_unstable = is_api_unstable(next_api)
                    if not unstable and next_unstable:
                        late_unstable_count += 1
                    if unstable and not next_unstable:
                        stabalized_count += 1
                    if unstable and next_unstable and not is_ruf_same(api, next_api):
                        change_ruf_count += 1
                    if is_api_same(api, next_api):
                        same_count += 1
                        if unstable and next_unstable:
                            same_unstable_count += 1
                    else:
                        modify_count += 1
                        if unstable and next_unstable:
                            modify_unstable_count += 1
                        # if not ('pub fn ' not in api['api'] and 'pub fn ' in next_api['api']) \
                        #     and not ('pub fn ' in api['api'] and 'pub fn ' not in next_api['api']):
                        #     # print('API Changed')
                        #     # print('Old:', api)
                        #     # print('New:', next_api)
                        #     truemodify_count += 1
            # print_removed_api_info(i, api_list, new_api_list)
        if index > 0:
            new_api_count = api_count - remained_api_count
            new_unstable_count = unstable_api_count - remained_unstable_api_count
            # truenew_api = count_truenew_api(docs[index-1], docs[index])
        else:
            new_api_count = 0
            new_unstable_count = 0
            # truenew_api = -1
        remained_api_count = same_count + modify_count
        remained_unstable_api_count = same_unstable_count + modify_unstable_count
        print('Version', '{:>2}'.format(i),
                'API Count', '{:>5}'.format(api_count),
                'Same', '{:>5}'.format(last_same_count),
                'Modify', '{:>5}'.format(last_modify_count), 
                'Removed', '{:>5}'.format(last_removed_count), 
                'New', '{:>5}'.format(new_api_count))
                # 'True Modify', '{:>5}'.format(truemodify_count), 
                # 'True Removed', '{:>5}'.format(trueremoved_count), 
                # 'True New', '{:>5}'.format(truenew_api))
        print('Unstable  ',
                'API Count', '{:>5}'.format(unstable_api_count),
                'Same', '{:>5}'.format(last_same_unstable_count),
                'Modify', '{:>5}'.format(last_modify_unstable_count), 
                'Removed', '{:>5}'.format(last_removed_unstable_count), 
                'New', '{:>5}'.format(new_unstable_count),
                'Late Unstable', '{:>5}'.format(last_late_unstable_count),
                'Stabilized', '{:>5}'.format(last_stabalized_count),
                'Change RUF', '{:>5}'.format(last_change_ruf_count))
        results[i] = {
            'Version': i,
            'API Count': api_count,
            'Same': last_same_count,
            'Modify': last_modify_count,
            'Removed': last_removed_count,
            'New': new_api_count,
            'Unstable API Count': unstable_api_count,
            'Unstable Same': last_same_unstable_count,
            'Unstable Modify': last_modify_unstable_count,
            'Unstable Removed': last_removed_unstable_count,
            'Unstable New': new_unstable_count,
            'Late Unstable': last_late_unstable_count,
            'Stabilized': last_stabalized_count,
            'Change RUF': last_change_ruf_count
        }

        last_api_count = api_count
        last_same_count = same_count
        last_modify_count = modify_count
        last_removed_count = removed_count
        last_trueremoved_count = trueremoved_count
        last_truemodify_count = truemodify_count
        last_same_unstable_count = same_unstable_count
        last_modify_unstable_count = modify_unstable_count
        last_removed_unstable_count = removed_unstable_count
        last_late_unstable_count = late_unstable_count
        last_stabalized_count = stabalized_count
        last_change_ruf_count = change_ruf_count

    return results
        # if i != MAX_VERSION: 
            # classify_removed_api_info(docs[index], docs[index+1])
        # print_new_module_info(docs[index], docs[index+1])
            # # Print Changed API
            # print('Submodule:', submodule_path)
            # for api in api_list:
            #     if api['next_api_index'] == -1:
            #         print(api)

            # # Print All API
            # print('Submodule:', submodule_path)
            # print('--------Old------')
            # print(*api_list, sep='\n')
            # print('--------New------')
            # print(*new_api_list, sep='\n')
            # print('------------------')



def unchaged_api_duration_analysis(docs:dict, MIN_VERSION, MAX_VERSION):
    '''
    Analyze the duration of unchanged APIs.
    '''
    results_allapis = {}
    results_allapis_removed = {}
    results_allapis_unstable = {}
    results_unstable_removed = {}
    for i in range(MIN_VERSION, MAX_VERSION+1):
        index = i - MIN_VERSION
        duration_distribution = {}
        duration_distribution_removed = {}
        duration_distribution_unstable = {}
        duration_distribution_unstable_removed = {}
        for (submodule_path, plain_submodule) in docs[index].items():
            api_list = plain_submodule['plain_apis']
            for api in api_list:
                duration = api['duration']
                duration_distribution[duration] = duration_distribution.get(duration, 0) + 1
                if api['next_api_index'] == -1:
                    duration_distribution_removed[duration] = duration_distribution_removed.get(duration, 0) + 1
                if is_api_unstable(api):
                    duration_distribution_unstable[duration] = duration_distribution_unstable.get(duration, 0) + 1
                    if api['next_api_index'] == -1:
                        duration_distribution_unstable_removed[duration] = duration_distribution_unstable_removed.get(duration, 0) + 1
        results_allapis[i] = distribution_summary(duration_distribution)
        results_allapis_removed[i] = distribution_summary(duration_distribution_removed)
        results_allapis_unstable[i] = distribution_summary(duration_distribution_unstable)
        results_unstable_removed[i] = distribution_summary(duration_distribution_unstable_removed)
    print('All APIs Duration Summary')
    for (version, summary) in results_allapis.items():
        print('Version', '{:>2}'.format(version), 'Average Duration', '{:.5}'.format(summary['average']), 'Total Count',  '{:>5}'.format(summary['total']))
    print('All APIs Removed Duration Summary')
    for (version, summary) in results_allapis_removed.items():
        print('Version', '{:>2}'.format(version), 'Average Duration', '{:.5}'.format(summary['average']), 'Total Count',  '{:>5}'.format(summary['total']))
    print('All Unstable APIs Duration Summary')
    for (version, summary) in results_allapis_unstable.items():
        print('Version', '{:>2}'.format(version), 'Average Duration', '{:.5}'.format(summary['average']), 'Total Count',  '{:>5}'.format(summary['total']))
    print('All Unstable APIs Removed Duration Summary')
    for (version, summary) in results_unstable_removed.items():
        print('Version', '{:>2}'.format(version), 'Average Duration', '{:.5}'.format(summary['average']), 'Total Count',  '{:>5}'.format(summary['total']))
        

def distribution_summary(durations: dict):
    '''
    Summarize the distribution of API duration.
    '''
    results = {}
    total = 0
    total_duration = 0
    for (duration, count) in durations.items():
        total += count
        total_duration += duration * count
    if total == 0:
        return {'average': 0, 'total': 0}
    results['average'] = total_duration / total
    results['total'] = total
    return results
        

def analyze_api_evolution(docs:dict, MIN_VERSION, MAX_VERSION):
    '''
    !!!MAIN FUNTION!!!:

    Analyze the API evolution in different ways, aspects. (API change, Stability change, etc)
    1. Quick check same: Complete same.
    2. Detailed check same: API unchanged. Other changes are acceptable.
    3. Modified: API name same, but signature changed.
    4. Removed: API removed.
    We then compare the API evolution with the stability evolution to see if they really match.
    Some API are duplicated, but with limited impact. 
        Some are OK as ducumentation record is duplicated sometimes (rarely found).
        Some are caused by duplicated info extraction (rarely found).
    
    '''
    print('Start Analyzing API Evolution ...')
    construct_api_binding(docs, MIN_VERSION, MAX_VERSION)
    # unchaged_api_duration_analysis(docs, MIN_VERSION, MAX_VERSION)
    # api_evolution_analysis(docs, MIN_VERSION, MAX_VERSION)
    # statistics_removed_api_info()


# TODO: Think carefully about the algorithm of abnormal RUF lifetime.
def api_evolution_analysis(docs:dict, MIN_VERSION, MAX_VERSION):
    '''
    Analyze the stability evolution in different ways, aspects. (Stability change, etc).
    Traditional Evolution:
    1. Stabilized
    2. Stay Unstable
    3. Deprecated
    4. Removed
    Abnormal Evolution:
    1. Change RUF
    2. Late Unstable
    3. Not Deprecated before Removed
    '''
    print('API Evolution (Lifetime) Analysis ...')
    # Do not analyze the last version. It's meaningless for lifetime analysis.
    total = 0
    unstable = 0
    removed = 0
    deprecated = 0
    stabilized = 0
    change_ruf = 0
    late_unstable = 0
    unstable_twice = 0
    not_deprecated_before_removed = 0
    revoked_deprecated = 0
    for i in range(MIN_VERSION, MAX_VERSION):
        index = i - MIN_VERSION
        for (submodule_path, plain_submodule) in docs[index].items():
            api_list = plain_submodule['plain_apis']
            for api in api_list:
                # Begin of an API. Get its lifetime.
                if api['duration'] == 0:
                    lifetime = [api]
                    next_api_index = api['next_api_index']
                    is_removed = -1
                    for j in range(i+1, MAX_VERSION):
                        if next_api_index == -1:
                            is_removed = j
                            break
                        next_index = j - MIN_VERSION
                        next_api = docs[next_index][submodule_path]['plain_apis'][next_api_index]
                        next_api_index = next_api['next_api_index']
                        lifetime.append(next_api)
                    # Analysis: Currently only unstable
                    results = analyze_single_api_lifetime(lifetime)
                    total += 1
                    if results['unstable'] != -1:
                        unstable += 1
                    # else:
                    #     continue
                    if is_removed != -1:
                        removed += 1
                    if results['deprecated'] != -1:
                        deprecated += 1
                    if results['stabilized'] != -1:
                        stabilized += 1
                    if results['change_ruf'] != -1:
                        change_ruf += 1
                    if results['late_unstable'] != -1:
                        late_unstable += 1
                    if results['unstable_twice'] != -1:
                        unstable_twice += 1
                    if results['not_deprecated_before_removed'] != -1  and is_removed != -1:
                        not_deprecated_before_removed += 1
                    if results['revoked_deprecated'] != -1:
                        revoked_deprecated += 1
    print('Total', total, 'Unstable', unstable, 'Stabilized', stabilized, 'Deprecated', deprecated, 'Removed', removed)
    print('Change RUF', change_ruf, 'Late Unstable', late_unstable, 'Unstable Twice', unstable_twice, 'Not Deprecated Before Removed', not_deprecated_before_removed, 'Revoked Deprecated', revoked_deprecated)


                    

                    

def analyze_single_api_lifetime(lifetime: list):
    results = {
        'unstable': -1,
        'deprecated': -1,
        'stabilized': -1,
        'change_ruf': -1,
        'late_unstable': -1,
        'unstable_twice': -1,
        'not_deprecated_before_removed': -1,
        'revoked_deprecated': -1,
    }
    for i in range(len(lifetime)-1):
        api = lifetime[i]
        next_api = lifetime[i+1]
        unstable = is_api_unstable(api)
        next_unstable = is_api_unstable(next_api)
        if unstable:
            results['unstable'] = i
        if unstable and not next_unstable:
            results['stabilized'] = i
        if is_api_deprecated(api):
            results['deprecated'] = i
        # Abnormal
        if unstable and next_unstable and not is_ruf_same(api, next_api):
            results['change_ruf'] = i
        if not unstable and next_unstable:
            results['late_unstable'] = i
            if results['unstable'] != -1:
                results['unstable_twice'] = i
        if not is_api_deprecated(api) and next_api['next_api_index'] == -1:
            results['not_deprecated_before_removed'] = i 
        if is_api_deprecated(api) and not is_api_deprecated(next_api):
            results['revoked_deprecated'] = i
    if not is_api_deprecated(lifetime[-1]):
        results['not_deprecated_before_removed'] = len(lifetime) - 1
    return results



def plain_all_docs(MIN_VERSION = 1, MAX_VERSION = 63):
    '''
    Parse all rustdocs to get items data in different compiler versions.
    These data are actually Abstract Resource Tree. Through analysing AST, we can know API evolution, especially unstable API.
    @Algorithm:
    1. We first parse root doc and call `get_crates()` to get all standard library crates, which we will then parse them.
    2. We call `parse_html()` to parse all html files, which contain AST of all data (e.g. modules, primitives, functions, structs).

    '''
    print('Start Analyzing Rust Docs ...')
    docs = list() # Each version of docs
    for i in range(MIN_VERSION, MAX_VERSION+1):
        version_num = '1.' + str(i) + '.0'
        print('Parsing Rust Docs', version_num)
        # Find root html: std/index.html
        current_directory = os.getcwd() + '/'
        doc_directory = current_directory + version_num + '/rust-docs-nightly-x86_64-unknown-linux-gnu/json_submodule'
        submodule_map = {} # Map submodule path to submodule
        for file_name in glob(doc_directory + '/**/*.html.json', recursive=True):
            with open(file_name, 'r') as file:
                submodule_original = json.load(file)
            (submodule_path, submodule_plain) = recover_info(submodule_original)
            submodule_map[submodule_path] = submodule_plain
        docs.append(submodule_map)
    with open('all_docs.json', 'w') as file:
        json.dump(docs, file)
    # for doc in docs:
    #     for (submodule_path, api_list) in doc.items():
    #         print('Submodule:', submodule_path)
    #         print(*api_list, sep='\n')
    #         print('------------------')





#TODO: Anylize the API evolution in different ways, aspects. (API change, Stability change, etc)
if sys.argv[1] == 'plain_apis':
    plain_all_docs()
if sys.argv[1] == 'plain_apis_selected':
    plain_all_docs(int(sys.argv[2]), int(sys.argv[3]))
if sys.argv[1] == 'complete':
    with open('all_docs.json', 'r') as file:
        docs = json.load(file)
    analyze_api_evolution(docs, 1, 63)
if sys.argv[1] == 'complete_selected':
    with open('all_docs.json', 'r') as file:
        docs = json.load(file)
    min = int(sys.argv[2])
    max = int(sys.argv[3])
    analyze_api_evolution(docs[min-1:max], min, max)
# with open('test_serial.json', 'r') as file:
#     submodule = json.load(file)
# print(*recover_info(submodule)[1], sep='\n')

'''
Findings:
    1. 1.4.0 -> 1.5.0 `libc` crates changed a lot, refactoring many submodules, causing lots of removals and new submodules.
    2. 1.16.0 -> 1.17.0 Some type in the trait has been changed, causing large-scale implementation changes.
    3. 1.18.0 -> 1.19.0 Trait `Iterator` changed provided functions, all implementations are affected.
    4. 1.24.0 -> 1.26.0 Arch-related API are introduced, like `core::arch` and `std::simd`.
    5. 1.27.0 -> 1.28.0 Arch-related API are removed, like `core::arch` and `std::simd`.
    6. 1.32.0 -> 1.33.0 4800 APIs are changed due to slight change of types or parameters of original traits.
    6. 1.33.0 -> 1.35.0 18780 new APIs add `default` before `fn`. In 1.35.0, lots are removed and go back to normal.
    6. 1.47.0 -> 1.48.0 `pub` is added into pub functions, though it is not needed, just for format.
    6. 1.51.0 -> 1.52.0 `pub` is now removed, though it is not needed, just for format.
    6. 1.56.0 -> 1.57.0 Abourt 3000 APIs in `core::simd::Simd` and another 3000 in `std::simd::Simd` are introduced. 
    6. 1.57.0 -> 1.58.0 Abourt 3000 APIs in `core::simd::Simd` and another 3000 in `std::simd::Simd` are removed. About 1200 APIs in `std::ops::xx` changed their types slightly.
    6. 1.62.0 -> 1.63.0 Abourt 4300 APIs change their `impl<'_ xxx>` to `impl xxx`.
'''