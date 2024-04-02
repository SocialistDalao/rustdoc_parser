import requests
import re
import tarfile
from datetime import datetime,timedelta
import os
import gzip
import urllib.request
import json


# Cannot print unicode corretly. Be sure that you know this.
def print_pretty(dict_item):
    print(json.dumps(dict_item, indent = 4, sort_keys=True))


def download_file(version_date, out_file, is_retry = False):
    url = 'https://static.rust-lang.org/dist/' + version_date + '/rust-docs-nightly-x86_64-unknown-linux-gnu.tar.gz'
    # Download archive
    try:
        # Read the file inside the .gz archive located at url
        with urllib.request.urlopen(url) as response:
            with gzip.GzipFile(fileobj=response) as uncompressed:
                file_content = uncompressed.read()

        # write to file in binary mode 'wb'
        with open(out_file, 'wb') as f:
            f.write(file_content)
            return 0
    # Retry +- 1 day: Sometimes the release day is not the same as the release file url, but within one day.
    except Exception as e:
        if is_retry == False:
            date_object = datetime.strptime(version_date, '%Y-%m-%d')
            if download_file((date_object+timedelta(days=1)).strftime('%Y-%m-%d'), out_file, True) == 0 \
                or download_file((date_object+timedelta(days=-1)).strftime('%Y-%m-%d'), out_file, True) == 0:
                    return 0
            else:
                print(e, url)
        return 1


def extract_file(fname, to_directory='.'):
    if fname.endswith("tar.gz"):
        tar = tarfile.open(fname)
        tar.extractall(to_directory)
        tar.close()


def crawl_rustdoc():
    r = requests.get('https://raw.githubusercontent.com/rust-lang/rust/master/RELEASES.md')
    text = r.text
    versions = re.findall("Version 1\.[0-9]+\.0 \([0-9]+-[0-9]+-[0-9]+\)", text)
    # `version` example: "Version 0.1  (2012-01-20)"
    print("Starting downloading rustdoc from " + versions[-2] + " to " + versions[0])
    for version in reversed(versions):
        version_list = version.split(' ')
        version_num = version_list[1]
        version_date = version_list[2].strip('(').strip(')')
        # v1.0.0 has no doc
        if version_num == '1.0.0':
            continue
        file_name = version_num + ".tar.gz"
        directory_name = version_num
        if os.path.exists(file_name):
            print("Version", version_num, "exists, skip...")
        else:
            print("Downloading v" + version_num + " ......")
            download_file(version_date, file_name)
        if os.path.exists(directory_name):
            print("Directory", version_num, "exists, skip...")
        else:
            print("Extracting v" + version_num + " ......")
            extract_file(file_name, directory_name)


# Step 2: Analyse html files. We extract RUF for every items. The items are under each html files.
# In this way, we only need to extract all html files and analyse them based on title, content, and others.
from glob import glob
from bs4 import BeautifulSoup, NavigableString
from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from webdriver_manager.firefox import GeckoDriverManager
import html




def empty_function():
    return {
        'api': '',
        'stability': list(),
    }


# `funtions` may not be functions. It is betther viewed as API. `impl` may indicate `fields` of structs, enums, unions.
def empty_impl():
    return {
        'impl': '',
        'functions': list() # -> function
    }

def empty_item():
    return {
        'head' : '',
        'impls' : list() # -> impl
    }

def empty_submodule():
    return {
        'kind': '',
        'path': '',
        'api': '',
        'stability': list(),
        'items': list(), # -> item
    }


def is_unstable(stability: list) -> int:
    return len(stability)



# Mappings of Kind -> API Type
# Note this includes most of them. We try to handle most of them, but still find some are missing.
# Refer to rustdoc source code `rust/src/librustdoc/html/render/print_items.rs` in Rust repo for more.
kind_mappings = {
    'Struct':   'struct',
    'Function': 'fn',
    'Trait':    'trait',
    'Type':     'typedef',
    'Macro':    'macro',
    'Enum':     'enum',
    'Constant': 'const',
    'Union':    'union',
    # Primitive and Keywork has no API 
}

# Mappings of API Type -> Kind
api_mappings = {
    'struct':   'Struct',
    'fn':       'Function',
    'trait':    'Trait',
    'typedef':  'Type',  
    'macro':    'Macro',
    'enum':     'Enum',  
    'const':    'Constant',
    'union':    'Union',
    # Primitive and Keywork has no API 
}



def get_unstable_count(submodule):
    unstable_count = 0
    unstable_count += is_unstable(submodule['stability'])
    for item in submodule['items']:
        for impl in item['impls']:
            for function in impl['functions']:
                unstable_count += is_unstable(function['stability'])
    return unstable_count



def get_items_count(submodule):
    count = 0
    for item in submodule['items']:
        count += len(item['impls'])
        for impl in item['impls']:
            count += len(impl['functions'])
    return count


def get_pres(soup):
    pre_list = list()
    for pre in soup.find_all('pre'):
        if len(pre.get('class', [])) == 2:
            pre_list.append(pre)
    return pre_list


# Check if the item is stability item.
# Return `None` if not. Return valid string if it is.
def get_stability(item, version_num) -> str:
    '''
    Check if the item is stability item.
    Return `None` if not. Return valid string if it is.
    Sometimes there will be multiple stability items. We return merged string since 1.48.0.
    We do this because only one of them are stability items and others are portability items.
    '''
    if item.name not in ['div', 'span']:
        return None
    item_class = item.get('class', [''])
    if version_num <= 48 and item_class[0] == 'stability':
        return item.text
    if version_num >= 49 and item_class[0] == 'item-info':
        return item.text
    return None



# Sometimes it includes `\u24d8` which is followed by notable-trait info, useless in our study.
def get_api(item, version_num = 0) -> str:
    if version_num >= 52:
        if item and item.h3 and item.h3.code:
            return item.h3.code.text
        elif item and item.h4:
            if item.h4.code:
                return item.h4.code.text
            return item.h4.text
        elif item and item.code:
            return item.code.text
        elif item and item.h3:
            return item.h3.text
        else:
            # print('cannot find api', item.text)
            return ''
    span = item.find('span', recursive = False)
    if span and span.code:
       return item.find('span', recursive = False).code.text
    code = item.find('code', recursive = False)
    if code:
        return code.text
    if not item.code:
        # Some fields (very few) cannot be successfully parsed.
        # print('cannot find api', item)
        return ''
    return item.code.text




def parse_html_div_items(div, version_num, tag_type = None) -> list:
    '''
    Parse div items, including `impl xxx` or `impl xxx for xxx`. All div items are impls.
    &Input `soup` should be div items. `parse_tag` should be either `h3` or `h4`
    &Return all impl funtions in the `div`.
    '''
    # Check parse tags first.
    h3_start = div.find('h3', recursive = False)
    h4_start = div.find('h4', recursive = False)
    if h3_start and h4_start:
        print('div contains both h3 and h4')
    tag_start = h4_start
    parse_tag = 'h4'
    if h3_start:
        tag_start = h3_start
        parse_tag = 'h3'
    if tag_type:
        tag_start = div.find(tag_type, recursive = False)
        parse_tag = tag_type
    if not tag_start:
        return None
    
    function = empty_function()
    function['api'] = get_api(tag_start)
    function_list = list()
    for sibling in tag_start.next_siblings:
        if sibling.name == parse_tag:
            function_list.append(function.copy())
            function = empty_function()
            function['api'] = get_api(sibling)
            # if 'impl' in function['api']:
            #     print(sibling.text)
        stability = get_stability(sibling, version_num)
        if stability:
            function['stability'].append(stability)
        if sibling.name == 'h2': # Exit when out of scope
            break
    function_list.append(function.copy())
    return function_list



def is_fields_indiv(div) -> bool:
    if div.find('code', recursive = False):
        return True
    return False



def parse_fields_indiv(div, version_num) -> list:
    '''
    Data fields may be in 'div' since 1.38.0. We resolve it.
    '''
    function = empty_function()
    function['api'] = div.code.text
    function_list = list()
    for sibling in div.next_siblings:
        if sibling.name == 'div' and sibling.find('code', recursive = False):
            function_list.append(function.copy())
            function = empty_function()
            function['api'] = sibling.code.text
        stability = get_stability(sibling, version_num)
        if stability:
            function['stability'].append(stability)
        if sibling.name == 'h2':
            break
    function_list.append(function.copy())
    return function_list




# From 1.10.0 Data fields html tags become `span` organized.
# From 1.21.0 Implementations may be collapsed to `span` rather than in `div`
# From 1.38.0 Data fields are organized in `div` rather than `span`.
def parse_html_spanitems(first_span, version_num) -> list:
    '''
    span items occur in structs, enums, unions, xxx. We parse them seperately.
    Span items can also appear in collapsed impl functions.
    @Input: First span items
    @Return all fields in span items.
    '''
    if not first_span.code:
        return None
    div = first_span.find('div', recursive = False)
    if div:
        return parse_html_div_items(div, version_num)
    function = empty_function()
    function['api'] = first_span.code.text
    function_list = list()
    for sibling in first_span.next_siblings:
        if sibling.name == 'span':
            if not sibling.code:
                continue
            function_list.append(function.copy())
            function = empty_function()
            function['api'] = sibling.code.text
        stability = get_stability(sibling, version_num)
        if stability:
            function['stability'].append(stability)
        if sibling.name == 'h2': # Exit when out of scope
            break
    function_list.append(function.copy())
    return function_list



def process_fileds(tag, version_num) -> list:
    '''
    Enums, structs and other types may have its variables inside fields.
    The html tags of these fields are frequently changing. We handle this seperately.
    Return `None` if not recognized.
    '''
    function_list = list()
    if tag.name == 'table':
        for tr in tag.find_all('tr', recursive = False):
            function = empty_function()
            function['api'] = tr.code.text
            stabilities = tr.find_all('div', class_ = 'stability')
            for stability in stabilities:
                function['stability'].append(stability.text)
            function_list.append(function.copy())
        return function_list
    elif tag.name == 'span':
        return parse_html_spanitems(tag, version_num)
    else:
        return None


def is_details_collapsed(div, version_num = 0) -> str:
    '''
    Details items may be collapsed into `div`. We check it.
    This is first found in rustc 1.xx.0
    '''
    if not div.find('details', recursive = False):
        if div.find('section', recursive = False):
            return 'section'
        if div.find('div', recursive = False):
            for div_item in div.find_all('div', recursive = False):
                if div_item.find('code', recursive = False):
                    return 'div_div_code'
        return 'unknown'
    for detail in div.find_all('details', recursive = False):
        if detail.find('details', recursive = False):
            return 'collapsed'
        for inner_div in detail.find_all('div', recursive = False):
            if inner_div.find('details', recursive = False):
                return 'collapsed'
            if inner_div.find('section', recursive = False):
                return 'collapsed'
            if version_num == 53 and inner_div.find('div', recursive = False):
                return 'collapsed'
    return 'notcollapsed'


def is_h3h4_collapsed(div) -> bool:
    '''
    h3h4 items may be collapsed into `div`. We check it.
    This is first found in rustc 1.21.0
    '''
    for h3 in div.find_all('h3', recursive = False):
        for sibling in h3.next_siblings:
            if sibling.name == 'div':
                h4 = sibling.find('h4', recursive = False)
                if h4 and h4.code:
                    return True
            if sibling.name == 'h3':
                break
    return False



def parse_h3h4_indiv(div, version_num) -> list:
    '''
    h3h4 items may be collapsed into `div`. We check it.
    This is first found in rustc 1.21.0
    '''
    first_h3 = div.find('h3', recursive = False)
    impl_list = list()
    impl = empty_impl()
    impl['impl'] = first_h3.code.text
    for sibling in first_h3.next_siblings:
        if sibling.name == 'h3':
            impl = empty_impl()
            impl['impl'] = sibling.code.text
        if sibling.name == 'div':
            functions = parse_html_div_items(sibling, version_num)
            if functions:
                impl['functions'] = functions
                impl_list.append(impl.copy())
    return impl_list




def parse_single_detail_function(function_detail, version_num) -> dict:
    function = empty_function()
    for inner in function_detail.find_all(recursive = False):
        if inner.name == 'summary':
            if get_api(inner, version_num) == '':
                continue
            if version_num >= 52:
                for item in inner.find_all(recursive = False):
                    stability = get_stability(item, version_num)
                    if stability:
                        function['stability'].append(stability)
            function['api'] = get_api(inner, version_num)
        if function['api'] == '':
            function['api'] = get_api(inner, version_num)
        stability = get_stability(inner, version_num)
        if stability:
            function['stability'].append(stability)
    if function['api'] == '':
        alternative_api = get_api(function_detail, version_num)
        if version_num >= 52 and alternative_api != '':
            function['api'] = alternative_api
            # print('alternative api' ,alternative_api)
        else:
            print('No api found in single_detail_function', function_detail.text)
            return None
    return function


# Return `impl` item.
def parse_html_detail_impl_items(detail, version_num) -> dict:
    impl = empty_impl()
    if get_api(detail.find('summary', recursive = False), version_num) == '':
        print('cannot find impl head', detail.text)
    impl['impl'] = get_api(detail.find('summary', recursive = False), version_num)
    # print('impl:', impl['impl'])
    for possible_div in detail.find_all('div', recursive = False):
        if version_num == 53:
            for inner_div in possible_div.find_all('div', recursive = False):
                # print(inner_div.text)
                function = parse_single_detail_function(inner_div, version_num)
                if function:
                    impl['functions'].append(function.copy())
        for inner_detail in possible_div.find_all('details', recursive = False):
            # print(inner_detail.name)
            if inner_detail.find('details', recursive = False):
                for hidden_detail in inner_detail.find_all('details', recursive = False):
                    function = parse_single_detail_function(hidden_detail, version_num)
                    if function:
                        impl['functions'].append(function.copy())
            else:
                if version_num == 52:
                    for hidden_h4 in inner_detail.find_all('h4', recursive = False):
                        # print(hidden_h4.text)
                        function = parse_single_detail_function(hidden_h4, version_num)
                        if function:
                            impl['functions'].append(function.copy())
                else:
                    function = parse_single_detail_function(inner_detail, version_num)
                    if function:
                        impl['functions'].append(function.copy())
        for inner_section in possible_div.find_all('section', recursive = False):
            function = parse_single_detail_function(inner_section, version_num)
            if function:
                impl['functions'].append(function.copy())

    return impl


def parse_section_indiv(div, version_num) -> list:
    '''
    '''



def parse_html_h2items_details(h2, version_num) -> list:
    '''
    Since 1.52.0, impls are not stored in `h3` but `details` instead. Other formats change, too.
    We use this function to parse them.
    '''
    assert version_num >= 52, 'This function is only for version >= 1.52.0'
    impl = empty_impl()
    impl_list = list()
    # First, we check if they are specific cases
    if h2['id'] == 'variants':
        impl = empty_impl()
        function = empty_function()
        for sibling in h2.next_siblings:
            if sibling.name == 'div' and 'variant' in sibling.get('id', ''):
                if function['api'] != '':
                    impl['functions'].append(function.copy())
                function = empty_function()
                function['api'] = sibling.code.text
            stability = get_stability(sibling, version_num)
            if stability:
                function['stability'].append(stability)
            if sibling.name == 'h2': # Exit when out of scope
                if function['api'] != '':
                    impl['functions'].append(function.copy())
                impl_list.append(impl.copy())
                return impl_list

    for sibling in h2.next_siblings:
        if sibling.name == 'h2':
            return impl_list
        elif sibling.name == 'div':
            # We handle `trait` data type seperately as they are not listed in `details`
            if version_num == 52 and sibling.get('class', [''])[0] == 'methods':
                functions = parse_html_div_items(sibling, version_num)
                if functions:
                    impl['functions'] = functions
                    impl_list.append(impl.copy())
                    continue
            details_collapsed = is_details_collapsed(sibling, version_num)
            if details_collapsed == 'unknown':
                continue
            if details_collapsed == 'div_div_code':
                functions = parse_html_div_items(sibling, version_num, 'div')
                if functions:
                    impl['functions'] = functions
                    impl_list.append(impl.copy())
                    continue
            for div_item in sibling.find_all(recursive = False):
                if div_item.name == 'details':
                    if details_collapsed == 'collapsed':
                        impl = parse_html_detail_impl_items(div_item, version_num)
                        if impl:
                            impl_list.append(impl.copy())
                    else:
                        function = parse_single_detail_function(div_item, version_num)
                        if function:
                            impl['functions'].append(function.copy())
                elif div_item.name == 'h3':
                    print('h3 along with details in div', div_item.text)
                    impl = empty_impl()
                    if not div_item.code:
                        print(div_item.text)
                    impl['impl'] = get_api(div_item, version_num)
                    impl_list.append(impl.copy())
            if details_collapsed == 'notcollapsed':
                    impl_list.append(impl.copy())
                    impl = empty_impl()
        elif sibling.name == 'details':
            impl = parse_html_detail_impl_items(sibling, version_num)
            if impl:
                impl_list.append(impl.copy())
    return impl_list





# Since 1.49.0, `stability` items are stored in `div` with class `stab unstable`
# Since 1.52.0, impls are not stored in `h3` but `details` instead. Other formats change, too.
def parse_html_h2items(h2, version_num) -> list:
    '''
    Parse items under h2, including `Methods`, `Trait Implementations`, etc.
    The format may change in different rustdoc version, but not too much.
    &Input `soup` should be h2 items, sometimes directly start with h3.
    &Return all impl funtions in the `div`.
    Exceptions: 
        Some impl have no impl function (e.g., Debug, From).
        In this case, they have no 'h3'('impl') before 'div'.
        In the 'div', they contain 'h3'(traits) rather than 'h4'(functions).
    '''
    # Skip NavigableString (Comments or other useless info) to find next Tag item.
    # h3_start = h2.next_sibling
    # while h3_start and isinstance(h3_start, NavigableString):
    #     h3_start = h3_start.next_sibling
    # # h2 can only be followed by h3 or div(e.g. 'Trait Implementation')
    # if h3_start.name == 'h3':
    #     impl['impl'] = h3_start.code.text
    # else:
    #     assert h3_start.name == 'div', 'only h3 or div can follow h2, but find' + h3_start
    #     impl['functions'] fn ne<I>(self, other: I) -> bool = parse_html_div_items(sibling)
    #     impl_list.append(impl)
    # if version_num >= 52:
    #     impl_list = parse_html_h2items_details(h2, version_num)
    #     if len(impl_list) != 0:
    #         return impl_list
    impl = empty_impl()
    impl_list = list()
    for sibling in h2.next_siblings:
        if sibling.name == 'h2':
            return impl_list
        elif sibling.name == 'h3':
            impl = empty_impl()
            # Seems only occur in: ['Derived Implementations']
            if not sibling.code:
                if not sibling['id'] == 'derived_implementations':
                    print('h3 has no code ' + str(sibling))
                continue
            impl['impl'] = sibling.code.text
        elif sibling.name == 'div':
            # Collapsed impls are in `div` list.
            if version_num >= 21 and impl['impl'] == '' and is_h3h4_collapsed(sibling):
                return parse_h3h4_indiv(sibling, version_num)
            if version_num >= 38 and impl['impl'] == '' and is_fields_indiv(sibling):
                impl['functions'] =  parse_fields_indiv(sibling, version_num)
                impl_list.append(impl.copy())
                return impl_list
            functions = parse_html_div_items(sibling, version_num)
            if functions:
                impl['functions'] = functions
                impl_list.append(impl.copy())
        # 'Implementors' items are presented in `ul` list.
        elif sibling.name == 'ul':
            impl = empty_impl()
            assert 'implementors-list' in sibling['id']
            impl['impl'] = sibling['class'][0]
            functions = parse_html_div_items(sibling, 'li')
            if functions:
                impl['functions'] = functions
                impl_list.append(impl.copy())
        else:
            function_list = process_fileds(sibling, version_num)
            if function_list:
                impl['functions'] = function_list
                impl_list.append(impl.copy())
                return impl_list
    return impl_list



# Get submodule metadate (name, path, etc)
def parse_html_inband(soup, version_num):
    '''
    Get submodule metadate (kind, path, api, stability, and items). It is uniquely defined by `path`. You can assume it as its ID.
    @Input: Html bs. If it is a module, we won't process items, as items are submodules can will be processed seperately.
    @Output: Submodule metadata (`dict`). Maybe return `None` if cannot process.
    Exceptions to take care of:
    1. Submodule in-band may not contain its type in early rustdoc. In this way, we search for its api instead (pre['class'][1])
    2. In-band "Primitive", "Keyword" have no API, just like modules. We should handle them seperately.
        We better not assume they are the only exceptions. Currently, we search for Tag 'pre' with no class 'rust-example-rendered'
    '''
    # Path and Kind
    submodule = empty_submodule()
    span = soup.find('span', class_='in-band')
    if not span:
        # Some htmls have redirection. The html itself is empty.
        return None
    item = span.text.split()
    kind = ''
    path = ''
    if len(item) == 1:
        # No kind
        path = item[0]
    elif len(item) == 3:
        if item[0] not in ['Primitive', 'Type', 'Foreign']: 
            print("Complex kind detected", item)
        kind == item[0]
        path = item[2]
    else:
        assert len(item) == 2, 'Submodule metadata inband resolve error ' 
        kind == item[0]
        path = item[1]

    # API
    # Old rustdoc do not contain type. We search for api instead.
    api = ''
    api_type = ''
    for pre in get_pres(soup):
        if pre['class'][1] != 'rust-example-rendered':
            assert api == '', "Should not contain two api: " 
            api_type = pre['class'][1]
            api = pre.text
    
    # Try to recover `kind`` if it is missing. API missing is allowed.
    if kind == '' and api_type == '':
        return None
    if kind == '':
        if api_type not in api_mappings:
            return None
        else:
            kind = api_mappings[api_type]

    submodule['kind'] = kind
    submodule['path'] = path
    submodule['api'] = api
    # Stabilibty
    if version_num >= 58:
        head = soup.find('div', class_='main-heading')
    else:
        head = soup.find('h1', class_='fqn')
    for sibling in head.next_siblings:
        if sibling.name == 'h2':
            break
        stability = get_stability(sibling, version_num)
        if stability:
            submodule['stability'].append(stability)
    return submodule



# From 1.58.0, the header is not organized with the beginning of `h1` with class `fqn`.
def parse_html(html_path, version_num):
    '''
    Here we will parse html file, which may be a module or submodule (e.g. function, struct, enum).
    @Algorithm:
    1. We first call `parse_html_inband()` to get html metadata.
    2. Then, we parse all h2 items, which are implementations of the submodules.
    '''
    print('Parsing html', html_path)
    html_content = open(html_path, 'r').read()
    soup = BeautifulSoup(html_content, 'html.parser')

    # We don't analyse sepcial htmls.
    if 'all.html' in html_path:
        return None

    is_module = False
    if '/index.html' in html_path:
        is_module = True

    # Parse metadata
    submodule = parse_html_inband(soup, version_num)
    if submodule == None:
        return None
    
    # Parse all h2 items if submodules
    if not is_module:
        inner_list = list()
        if version_num >= 58:
            head = soup.find('div', class_='main-heading')
        else:
            head = soup.find('h1', class_='fqn')
        for sibling in head.next_siblings:
            if sibling.name == 'h2':
                inner = empty_item()
                inner['head'] = " ".join(sibling.text.split()) # head text contain duplicate spaces and new lines. We remove them.
                if version_num >= 52:
                    if inner['head'] not in ['Tuple Fields', 'Fields', 'Variants']:
                        impl_list = parse_html_h2items_details(sibling, version_num)
                        if len(impl_list) != 0:
                            inner['impls'] = impl_list
                if len(inner['impls']) == 0:
                    inner['impls'] = parse_html_h2items(sibling, version_num)
                inner_list.append(inner.copy())
        submodule['items'] = inner_list

    # Check if all ruf are collected
    collected_unstable_count = get_unstable_count(submodule)
    if version_num <= 48:
        stability_items = soup.find_all('div', class_='stability')
    elif version_num >= 61:
        stability_items = soup.find_all('span', class_='item-info')
    else:
        stability_items = soup.find_all('div', class_='item-info')
    html_unstable_count = len(stability_items)
    if collected_unstable_count != html_unstable_count:
        # print(html_path, 'misses unstable items' + str(submodule))
        print('misses unstable items', collected_unstable_count, html_unstable_count)
    return (submodule, collected_unstable_count, html_unstable_count)


def get_crates(doc_directory):
    '''
    Use brower engine to render the root html. In this way, we can get crates.
    '''
    std_index_path = doc_directory + '/std/index.html'
    # Use brower to render html to get full content
    # service = Service(GeckoDriverManager().install())
    # browser = webdriver.Firefox(service=service)
    service = Service('./geckodriver')
    browser = webdriver.Firefox(service=service)
    browser.get('file:///'+std_index_path)
    html = browser.page_source
    browser.quit()
    soup = BeautifulSoup(html, 'html.parser')
    crates = soup.find_all('a', class_='crate')
    crates_string = list()
    for crate in crates:
        crates_string.append(crate.string)
    return crates_string





def test_html_pre_types():
    '''
    Test Results:
    1. Submodule in-band may not contain its type in early rustdoc. In this way, we search for its api instead (pre['class'][1])
    2. All possible (in-band -> pre['class'][1]) found now: {'Macro': {'macro', 'rust-example-rendered'},
        'List': set(), 'Struct': {'struct', 'rust-example-rendered'}, 'Trait': {'trait', 'rust-example-rendered'},
        'Type': {'rust-example-rendered', 'typedef'}, 'Enum': {'rust-example-rendered', 'enum'},
        'Function': {'rust-example-rendered', 'fn'}, 'Constant': {'const', 'rust-example-rendered'},
        'Union': {'rust-example-rendered', 'union'}, 'Primitive': {'rust-example-rendered'}, 'Keyword': {'rust-example-rendered'}}
    3. In-band "Primitive", "Keyword" have no API, just like modules. We should handle them seperately. We better not assume they are the only exceptions.
    '''
    all_types = dict()

    MIN_VERSION = 40
    MAX_VERSION = 50
    for i in range(MIN_VERSION, MAX_VERSION+1):
        version_num = '1.' + str(i) + '.0'
        print('Parsing', version_num, '......')
        doc_directory = '/media/loancold/HardDisk/ProjectInDisk/rustdoc_html_parser/' + version_num + '/rust-docs-nightly-x86_64-unknown-linux-gnu/rust-docs/share/doc/rust/html'
        crates_item = get_crates(doc_directory)
        # Find all html
        for crate in crates_item:
            crate = crate.string
            if crate == 'test':
                continue
            crate_directory = doc_directory + '/' + crate
            for file_name in glob(crate_directory + '/**/*.html', recursive=True):
                html_content = open(file_name, 'r').read()
                soup = BeautifulSoup(html_content, 'html.parser')
                if 'index.html' in file_name:
                    continue
                span = soup.find('span', class_='in-band')
                if not span:
                    # Some htmls have redirection. The html itself is empty.
                    continue
                item = span.text.split()
                kind = item[0]
                if len(item) == 1:
                    continue
                kind_types = all_types.get(kind, set())
                for pre in get_pres(soup):
                    kind_types.add(pre['class'][1])
                all_types[kind] = kind_types
    print(all_types)



div_class_set = set()
# Check all possible `div` class
# Found real: 'impl-items', 'methods'. Some have no class, which remain a problem.
def test_div_types(html_path):
    print('Parsing html', html_path)
    html_content = open(html_path, 'r').read()
    soup = BeautifulSoup(html_content, 'html.parser')
    soup = soup.find('section', {'id' : 'main'})
    if not soup:
        return
    for div in soup.find_all('div'):
        div_class = div.get('class', [''])[0]
        div_class_set.add(div_class)
        if div_class not in ['impl-items', 'methods'] and \
            div_class not in ['docblock', 'stability', 'stab', 'important-traits', 'content'] \
            and div.find('code'):
            print('Has CODE', div_class, div)



stab_set = set()
def test_stab_items(html_path):
    # print('Parsing html', html_path)
    html_content = open(html_path, 'r').read()
    soup = BeautifulSoup(html_content, 'html.parser')
    soup = soup.find_all('div')
    for div in soup:
        div_class = div.get('class', [''])
        if div_class[0] == 'item-info':
            for stab in div.find_all('div', class_ = 'stab'):
                div_class_string = ''
                for div_class_item in stab.get('class', ['']):
                    div_class_string += div_class_item + ' '
                stab_set.add(div_class_string)





def parse_all_docs(MIN_VERSION = 1, MAX_VERSION = 63):
    '''
    Parse all rustdocs to get items data in different compiler versions.
    These data are actually Abstract Resource Tree. Through analysing AST, we can know API evolution, especially unstable API.
    @Algorithm:
    1. We first parse root doc and call `get_crates()` to get all standard library crates, which we will then parse them.
    2. We call `parse_html()` to parse all html files, which contain AST of all data (e.g. modules, primitives, functions, structs).

    '''
    for i in range(MIN_VERSION, MAX_VERSION+1):
        version_num = '1.' + str(i) + '.0'
        # Find root html: std/index.html
        current_directory = os.getcwd() + '/'
        doc_directory = current_directory + version_num + '/rust-docs-nightly-x86_64-unknown-linux-gnu/rust-docs/share/doc/rust/html'
        if i == 52: # This is exception
            crates_string = ['alloc', 'core', 'proc_macro', 'std']
        else:
            crates_string = get_crates(doc_directory)

        # Find all html
        total_unstable_collected = 0
        total_unstable_exist = 0
        for crate in crates_string:
            if crate == 'test':
                continue
            crate_directory = doc_directory + '/' + crate
            for file_name in glob(crate_directory + '/**/*.html', recursive=True):
                tuples = parse_html(file_name, i)
                if tuples == None:
                    continue
                (submodule, collected_unstable_count, html_unstable_count) = tuples
                total_unstable_collected += collected_unstable_count
                total_unstable_exist += html_unstable_count
                # Store submodule data into json
                root_directory = file_name.split('rust-docs/share/doc/rust/html')[0]
                relative_directory = file_name.split('rust-docs/share/doc/rust/html')[1]
                json_file_path = root_directory + 'json_submodule' + relative_directory + '.json'
                print(json_file_path)
                os.makedirs(os.path.dirname(json_file_path), exist_ok=True)
                with open(json_file_path, 'w+') as file:
                    json.dump(submodule, file)
                # test_div_types(file_name)
                # test_stab_items(file_name)
                # print(stab_set)
                # print(stab_set)
        print(version_num, total_unstable_collected, total_unstable_exist)


# parse_all_docs(60,63)
# crawl_rustdoc()
# test_html_pre_types()
# parse_all_docs()
# print(div_class_set)
# print_pretty(parse_html('/home/loancold/Projects/rustdoc_parser/1.52.0/rust-docs-nightly-x86_64-unknown-linux-gnu/rust-docs/share/doc/rust/html/core/result/struct.Iter.html', 52))
import sys
if sys.argv[1] == 'complete':
    parse_all_docs()
elif sys.argv[1] == 'complete_selected':
    parse_all_docs(int(sys.argv[2]), int(sys.argv[3]))
elif sys.argv[1] == 'test_serial':
    submodule = parse_html(sys.argv[2], int(sys.argv[3]))[0]
    with open('test_serial.json', 'w') as file:
        json.dump(submodule, file)
else:
    print_pretty(parse_html(sys.argv[1], int(sys.argv[2]))[0])

'''
Found issue:
    1. `std::ptr::Unique` and `std::ptr::Shared` have duplicate items in h2 `Methods from Deref<Target=*mut T>`, from 1.2.0 to 1.7.0
    We dismiss it.
    2. Recursive data type definitions. Such as `core::ops::RangeInclusive` from 1.8.0 to 1.17.0, `'std::heap::AllocErr'` from 1.19.0 to 1.25.0, 'alloc::collections::TryReserveError' from 1.38.0 to 1.48.0
'''