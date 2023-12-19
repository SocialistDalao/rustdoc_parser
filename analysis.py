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
        'next_abi_index': -1, # Index of the same abi in next doc version in the same submodule. 
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
            stability_list.append(new_stability)
        # Unstable 2
        for matched_unstable in re.findall('🔬 This is a nightly-only experimental API\.\s\(\w+\)', item):
            # print('Unstable 2')
            unstable_part = re.search('\(\w+\)', matched_unstable)[0]
            ruf = unstable_part.split(' ')[0][1:-1]
            new_stability = empty_stability()
            new_stability['ruf'] = ruf
            new_stability['status'] = 'unstable'
            stability_list.append(new_stability)
        # Unstable 3: Unstable (wait_timeout_with #27748): unsure if this API is broadly needed or what form it should take\n
        for matched_unstable in re.findall('Unstable \(\w+ #[0-9]+\)', item):
            # print('Unstable 3')
            unstable_part = re.search('\(\w+ #[0-9]+\)', matched_unstable)[0]
            ruf = unstable_part.split(' ')[0][1:-1]
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
        for matched_unstable in re.findall('Deprecated since 1.[0-9]+.[0-9]+: .+\n', item):
            since = re.search('1.[0-9]+.[0-9]+', matched_unstable)[0]
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
def recover_info(submodule) -> (str, list):
    """
    Recover the information of a submodule from analysis results.
    Return a list containing minimal APIs.
    We do extra operations to eliminate the redundancy of the results.
    1. Sometimes it includes `\u24d8` which is followed by notable-trait info, useless in our study.
    2. Stability includes portability, deprecate, unstable items. We only latter two.
    """
    api_list = list()
    submodule_path = get_pure_string(submodule['path'])
    stability = submodule['stability']
    submodule_api = empty_api()
    submodule_api['submodule'] = submodule_path
    submodule_api['api'] = get_pure_string(submodule['api'])
    submodule_api['stability'] = analyze_stability(stability)
    # TODO: Now, we don't add submodule into the list.
    # api_list.append(submodule_api)
    for item in submodule['items']:
        head = item['head']
        for impl in item['impls']:
            impl_name = impl['impl']
            for function in impl['functions']:
                api = function['api']
                # if 'impl' in api:
                    # print('Warning: impl in api', api)
                api = api.split('\u24d8')[0]
                stability = function['stability']
                api_info = empty_api()
                api_info['submodule'] = submodule_path
                api_info['head'] = head
                api_info['impl'] = get_pure_string(impl_name)
                api_info['api'] = get_pure_string(api)
                api_info['stability'] = analyze_stability(stability)
                api_list.append(api_info)
    return (submodule_path, api_list)
    


def is_api_same(api1: dict, api2: dict) -> bool:
    return api1['impl'] == api2['impl'] and api1['api'] == api2['api']



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


def print_removed_api_info(api_list: list, new_api_list: list):
    '''
    Print removed API info.
    '''
    index_set = set()
    for api in api_list:
        next_abi_index = api['next_abi_index']
        if next_abi_index == -1:
            print('Removed API:', api)
        else:
            index_set.add(next_abi_index)
    for idx, api in enumerate(new_api_list):
        if idx not in index_set:
            print('New API:', api)



def print_new_module_info(doc:dict, doc_new:dict):
    '''
    Print new module info.
    '''
    for (submodule_path, api_list) in doc_new.items():
        if submodule_path not in doc:
            print('New Module:', submodule_path, len(api_list))
            print(*api_list, sep='\n')
            print('------------------')


def count_truenew_api(doc:dict, doc_new:dict):
    '''
    Count the number of new API in doc_new, which are not in doc.
    We remove `Implementors` as they are passively implemented, determined by traits.
    Sometimes it cannot reflect true api changes.
    '''
    count = 0
    for (submodule_path, api_list) in doc.items():
        if submodule_path not in doc_new:
            continue
        index_set = set()
        new_api_list = doc_new[submodule_path]
        for api in api_list:
            next_abi_index = api['next_abi_index']
            index_set.add(next_abi_index)
        for idx, api in enumerate(new_api_list):
            if idx not in index_set and api['head']  not in ['Implementors', 'Blanket Implementations']:
                count += 1
    for (submodule_path, api_list) in doc_new.items():
        if submodule_path not in doc:
            count += len(api_list)
    return count



def construct_api_binding(docs:list, MIN_VERSION, MAX_VERSION):
    '''
    Connect the API evolution in different versions.
    '''
    remained_api_count = 0
    for i in range(MIN_VERSION, MAX_VERSION):
        index = i - MIN_VERSION
        api_count = 0
        same_count = 0
        modify_count = 0
        removed_count = 0
        trueremoved_count = 0
        truemodify_count = 0
        for (submodule_path, api_list) in docs[index].items():
            api_count += len(api_list)
            # Removed submodule
            if submodule_path not in docs[index+1]:
                # print('Removed Submodule:', submodule_path, len(api_list))
                removed_count += len(api_list)
                continue
            new_api_list = docs[index+1][submodule_path]
            for api in api_list:
                for idx, new_api in enumerate(new_api_list):
                    if is_same_api(api, new_api):
                        if api['next_abi_index'] != -1:
                            # print('Error: next_abi_index already set', api['submodule'], api['api'])
                            break
                        api['next_abi_index'] = idx
            # analyze_api_evolution
            for api in api_list:
                if api['next_abi_index'] == -1:
                    removed_count += 1
                    if api['head'] not in ['Implementors', 'Blanket Implementations']:
                        trueremoved_count += 1
                else:
                    next_api = docs[index+1][submodule_path][api['next_abi_index']]
                    if is_api_same(api, next_api):
                        same_count += 1
                    else:
                        modify_count += 1
                        if not ('pub fn ' not in api['api'] and 'pub fn ' in next_api['api']) \
                            and not ('pub fn ' in api['api'] and 'pub fn ' not in next_api['api']):
                            # print('API Changed')
                            # print('Old:', api)
                            # print('New:', next_api)
                            truemodify_count += 1
            print_removed_api_info(api_list, new_api_list)
        # print_new_module_info(docs[index], docs[index+1])
        if index > 0:
            new_api_count = api_count - remained_api_count
            truenew_api = count_truenew_api(docs[index-1], docs[index])
        else:
            new_api_count = -1
            truenew_api = -1
        remained_api_count = same_count + modify_count
        print('Version', '{:>2}'.format(i), 'API Count', api_count,
                'Same', '{:>5}'.format(same_count),
                'Modify', '{:>5}'.format(modify_count), 
                'Removed', '{:>5}'.format(removed_count), 
                'New', '{:>5}'.format(new_api_count), 
                'True Modify', '{:>5}'.format(truemodify_count), 
                'True Removed', '{:>5}'.format(trueremoved_count), 
                'True New', '{:>5}'.format(truenew_api))
            # # Print Changed API
            # print('Submodule:', submodule_path)
            # for api in api_list:
            #     if api['next_abi_index'] == -1:
            #         print(api)

            # # Print All API
            # print('Submodule:', submodule_path)
            # print('--------Old------')
            # print(*api_list, sep='\n')
            # print('--------New------')
            # print(*new_api_list, sep='\n')
            # print('------------------')


def analyze_api_evolution(docs:list, MIN_VERSION, MAX_VERSION):
    '''
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
    # for i in range(MIN_VERSION, MAX_VERSION):
    #     index = i - MIN_VERSION
    #     api_count = 0
    #     same_count = 0
    #     modify_count = 0
    #     removed_count = 0
    #     for (submodule_path, api_list) in docs[index].items():
    #         api_count += len(api_list)
    #         for api in api_list:
    #             if api['next_abi_index'] == -1:
    #                 removed_count += 1
    #             else:
    #                 next_api = docs[index+1][submodule_path][api['next_abi_index']]
    #                 if is_api_same(api, next_api):
    #                     same_count += 1
    #                 else:
    #                     modify_count += 1
    #     print('Version', i, 'API Count', api_count, 'Same', same_count, 'Modify', modify_count, 'Removed', removed_count)




def analyze_all_docs(MIN_VERSION = 1, MAX_VERSION = 63):
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
    analyze_api_evolution(docs, MIN_VERSION, MAX_VERSION)
    # for doc in docs:
    #     for (submodule_path, api_list) in doc.items():
    #         print('Submodule:', submodule_path)
    #         print(*api_list, sep='\n')
    #         print('------------------')





#TODO: Anylize the API evolution in different ways, aspects. (API change, Stability change, etc)
if sys.argv[1] == 'complete':
    analyze_all_docs()
if sys.argv[1] == 'complete_selected':
    analyze_all_docs(int(sys.argv[2]), int(sys.argv[3]))
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
    6. 1.33.0 -> 1.35.0 18780 new APIs add `default` before `fn`. In 1.35.0, lots are removed and go back to normal.
    6. 1.47.0 -> 1.48.0 `pub` is added into pub functions, though it is not needed, just for format.
    6. 1.51.0 -> 1.52.0 `pub` is now removed, though it is not needed, just for format.
    6. 1.56.0 -> 1.57.0 Abourt 3000 APIs in `core::simd::Simd` and another 3000 in `std::simd::Simd` are introduced. 
    6. 1.57.0 -> 1.58.0 Abourt 3000 APIs in `core::simd::Simd` and another 3000 in `std::simd::Simd` are removed. About 1200 APIs in `std::ops::xx` changed their types slightly.
'''