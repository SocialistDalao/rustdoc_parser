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


# `funtions` not not be functions. `impl` may indicate `fields` of structs, enums, unions.
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






def parse_html_div_items(div, parse_tag) -> list:
    '''
    Parse div items, including `impl xxx` or `impl xxx for xxx`. All div items are impls.
    &Input `soup` should be div items. `parse_tag` should be either `h3` or `h4`
    &Return all impl funtions in the `div`.
    '''
    h4_start = div.find(parse_tag, recursive=False)
    if not h4_start:
        return list()
    function = empty_function()
    # print(h4_start)
    function['api'] = h4_start.code.text
    function_list = list()
    for sibling in h4_start.next_siblings:
        if sibling.name == parse_tag:
            function_list.append(function)
            function = empty_function()
            function['api'] = sibling.code.text
        if sibling.name == 'div' and sibling['class'][0] == 'stability':
            function['stability'].append(sibling.text)
        if sibling.name == 'h2': # Exit when out of scope
            break
    function_list.append(function)
    return function_list



def parse_html_spanitems(first_span) -> list:
    '''
    span items occur in structs, enums, unions, xxx. We parse them seperately.
    @Input: First span items
    @Return all fields in span items.
    '''
    function = empty_function()
    function['api'] = first_span.code.text
    function_list = list()
    for sibling in first_span.next_siblings:
        if sibling.name == 'span':
            function_list.append(function)
            function = empty_function()
            function['api'] = sibling.code.text
        if sibling.name == 'div' and sibling['class'][0] == 'stability':
            function['stability'].append(sibling.text)
        if sibling.name == 'h2': # Exit when out of scope
            break
    function_list.append(function)
    return function_list



def process_fileds(tag, version_num) -> list:
    '''
    Enums, structs and other types may have its variables inside fields.
    The html tags of these fields are frequently changing. We handle this seperately.
    '''
    function_list = list()
    if tag.name == 'table':
        for tr in tag.tbody.find_all('tr', recursive = False):
            function = empty_function()
            function['api'] = tr.code.text
            stability = tr.find('div', class_ = 'stability')
            if stability:
                function['stability'].append(sibling.text)
    # TODO
    return function_list


def parse_html_h2items(h2) -> list:
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

    impl = empty_impl()
    # if h2.name == 'h3' and h2.code: # Probably start with h3 directly.
    #     impl['impl'] = h2.code.text
    impl_list = list()
    # If the first item is `span`. It means we are dealing with fileds.
    sibling = h2.next_sibling
    if sibling.name == 'span':
        impl = empty_impl()
        impl['impl'] = " ".join(sibling.text.split()) # same as h2 header
        impl['functions'] = parse_html_spanitems(sibling)
        impl_list.append(impl)
        return impl_list

    for sibling in h2.next_siblings:
        if sibling.name == 'h2':
            return impl_list
        if sibling.name == 'h3':
            impl = empty_impl()
            # Seems only occur in: ['Derived Implementations']
            if not sibling.code:
                print('h3 has no code ' + str(sibling))
                continue
            impl['impl'] = sibling.code.text
        if sibling.name == 'div':
            if impl['impl'] == '':
                # print('h3')
                # return parse_html_h2items(sibling.find('h3', recursive = False))
                impl['functions'] = parse_html_div_items(sibling, 'h3')
            else:
                impl['functions'] = parse_html_div_items(sibling, 'h4')
            # if len(impl['functions']) == 0:
            #     print('Empty impl functions found', impl['impl'])
            impl_list.append(impl)

        # `Span` items are presented when 'div' items are set autohide
        if sibling.name == 'span':
            if sibling['class'][0] == 'loading-content':
                continue
            else:
                assert len(impl['functions']) == 0, 'div has functions and span is found'
            if impl['impl'] == '':
                impl['functions'] = parse_html_div_items(sibling.div, 'h3')
            else:
                impl['functions'] = parse_html_div_items(sibling.div, 'h4')
            impl_list.append(impl)

        # 'Implementors' items are presented in `ul` list.
        if sibling.name == 'ul':
            impl = empty_impl()
            assert sibling['id'] == 'implementors-list'
            impl['impl'] = sibling['class'][0]
            impl['functions'] = parse_html_div_items(sibling, 'li')
            impl_list.append(impl)

    return impl_list



# Get submodule metadate (name, path, etc)
def parse_html_inband(soup):
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
        assert item[0] == 'Primitive' or item[0] == 'Type', "Complex kind logic wrong"
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
    head = soup.find('h1', class_='fqn')
    for sibling in head.next_siblings:
        if sibling.name == 'h2':
            break
        if sibling.name == 'div' and sibling['class'][0] == 'stability':
            submodule['stability'].append(sibling.text)
            break
    return submodule




def parse_html(html_path):
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
    if 'index.html' in html_path:
        is_module = True

    # Parse metadata
    submodule = parse_html_inband(soup)
    if submodule == None:
        return None
    
    # Parse all h2 items if submodules
    if not is_module:
        inner_list = list()
        head = soup.find('h1', class_='fqn')
        for sibling in head.next_siblings:
            if sibling.name == 'h2':
                inner = empty_item()
                inner['head'] = " ".join(sibling.text.split()) # head text contain duplicate spaces and new lines. We remove them.
                inner['impls'] = parse_html_h2items(sibling)
                inner_list.append(inner)
        submodule['items'] = inner_list

    # Check if all ruf are collected
    collected_unstable_count = get_unstable_count(submodule)
    stability_items = soup.find_all('div', class_='stability')
    html_unstable_count = len(stability_items)
    if collected_unstable_count != html_unstable_count:
        print('misses unstable items' + str(submodule))

    # Check if all codes (impl) are collected.
    # collected_items_count = get_items_count(submodule)
    # code_items = soup.find_all('code')
    # code_count = len(code_items)
    # if collected_items_count != code_count:
    #     print('misses code items', 'collected->code items',collected_items_count, code_count, str(submodule))

    return submodule


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
    return soup.find_all('a', class_='crate')





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



def parse_all_docs():
    '''
    Parse all rustdocs to get items data in different compiler versions.
    These data are actually Abstract Resource Tree. Through analysing AST, we can know API evolution, especially unstable API.
    @Algorithm:
    1. We first parse root doc and call `get_crates()` to get all standard library crates, which we will then parse them.
    2. We call `parse_html()` to parse all html files, which contain AST of all data (e.g. modules, primitives, functions, structs).

    '''
    MIN_VERSION = 3
    MAX_VERSION = 20
    for i in range(MIN_VERSION, MAX_VERSION+1):
        version_num = '1.' + str(i) + '.0'
        # Find root html: std/index.html
        doc_directory = '/media/loancold/HardDisk/ProjectInDisk/rustdoc_html_parser/' + version_num + '/rust-docs-nightly-x86_64-unknown-linux-gnu/rust-docs/share/doc/rust/html'
        crates_item = get_crates(doc_directory)

        # Find all html
        for crate in crates_item:
            crate = crate.string
            if crate == 'test':
                continue
            crate_directory = doc_directory + '/' + crate
            for file_name in glob(crate_directory + '/**/*.html', recursive=True):
                parse_html(file_name)
                # test_div_types(file_name)


# test_html_pre_types()
parse_all_docs()
# print(div_class_set)
# print_pretty(parse_html('/media/loancold/HardDisk/ProjectInDisk/rustdoc_html_parser/1.42.0/rust-docs-nightly-x86_64-unknown-linux-gnu/rust-docs/share/doc/rust/html/alloc/rc/struct.Weak.html'))