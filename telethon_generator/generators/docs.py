#!/usr/bin/env python3
import os
import re
import sys
import shutil
try:
    from .docs_writer import DocsWriter
except (ImportError, SystemError):
    from docs_writer import DocsWriter

# Small trick so importing telethon_generator works
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from telethon_generator.parser import TLParser, TLObject


# TLObject -> Python class name
def get_class_name(tlobject):
    """Gets the class name following the Python style guidelines"""
    # Courtesy of http://stackoverflow.com/a/31531797/4759433
    name = tlobject.name if isinstance(tlobject, TLObject) else tlobject
    result = re.sub(r'_([a-z])', lambda m: m.group(1).upper(), name)

    # Replace '_' with '' once again to make sure it doesn't appear on the name
    result = result[:1].upper() + result[1:].replace('_', '')

    # If it's a function, let it end with "Request" to identify them more easily
    if isinstance(tlobject, TLObject) and tlobject.is_function:
        result += 'Request'

    return result


# TLObject -> filename
def get_file_name(tlobject, add_extension=False):
    """Gets the file name in file_name_format.html for the given TLObject.
       Only its name may also be given if the full TLObject is not available"""
    if isinstance(tlobject, TLObject):
        name = tlobject.name
    else:
        name = tlobject

    # Courtesy of http://stackoverflow.com/a/1176023/4759433
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    result = re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
    if add_extension:
        return result + '.html'
    else:
        return result


# TLObject -> from ... import ...
def get_import_code(tlobject):
    kind = 'functions' if tlobject.is_function else 'types'
    ns = '.' + tlobject.namespace if tlobject.namespace else ''

    return 'from telethon.tl.{}{} import {}'\
        .format(kind, ns, get_class_name(tlobject))


def get_create_path_for(tlobject):
    """Gets the file path (and creates the parent directories)
       for the given 'tlobject', relative to nothing; only its local path"""

    # Determine the output directory
    out_dir = 'methods' if tlobject.is_function else 'constructors'

    if tlobject.namespace:
        out_dir = os.path.join(out_dir, tlobject.namespace)

    # Ensure that it exists
    os.makedirs(out_dir, exist_ok=True)

    # Return the resulting filename
    return os.path.join(out_dir, get_file_name(tlobject, add_extension=True))


def is_core_type(type_):
    """Returns "true" if the type is considered a core type"""
    return type_.lower() in {
        'int', 'long', 'int128', 'int256', 'double',
        'vector', 'string', 'bool', 'true', 'bytes', 'date'
    }


def get_path_for_type(type_, relative_to='.'):
    """Similar to getting the path for a TLObject, it might not be possible
       to have the TLObject itself but rather its name (the type);
       this method works in the same way, returning a relative path"""
    if is_core_type(type_):
        path = 'index.html#%s' % type_.lower()

    elif '.' in type_:
        # If it's not a core type, then it has to be a custom Telegram type
        namespace, name = type_.split('.')
        path = 'types/%s/%s' % (namespace, get_file_name(name, True))
    else:
        path = 'types/%s' % get_file_name(type_, True)

    return get_relative_path(path, relative_to)


# Destination path from the current position -> relative to the given path
def get_relative_path(destination, relative_to):
    if os.path.isfile(relative_to):
        relative_to = os.path.dirname(relative_to)

    return os.path.relpath(destination, start=relative_to)


def get_relative_paths(original, relative_to):
    """Converts the dictionary of 'original' paths to relative paths
       starting from the given 'relative_to' file"""
    return {k: get_relative_path(v, relative_to) for k, v in original.items()}


# Generate a index.html file for the given folder
def find_title(html_file):
    """Finds the <title> for the given HTML file, or (Unknown)"""
    with open(html_file) as handle:
        for line in handle:
            if '<title>' in line:
                # + 7 to skip len('<title>')
                return line[line.index('<title>') + 7:line.index('</title>')]

    return '(Unknown)'


def build_menu(docs, filename, relative_main_index):
    """Builds the menu using the given DocumentWriter up to 'filename',
       which must be a file (it cannot be a directory)"""
    # TODO Maybe this could be part of DocsWriter itself, "build path menu"
    docs.add_menu('API', relative_main_index)

    items = filename.split('/')
    for i in range(len(items) - 1):
        item = items[i]
        link = '../' * (len(items) - (i + 2))
        link += 'index.html'
        docs.add_menu(item.title(), link=link)

    if items[-1] != 'index.html':
        docs.add_menu(os.path.splitext(items[-1])[0])
    docs.end_menu()


def generate_index(folder, original_paths):
    """Generates the index file for the specified folder"""

    # Determine the namespaces listed here (as sub folders)
    # and the files (.html files) that we should link to
    namespaces = []
    files = []
    for item in os.listdir(folder):
        if os.path.isdir(os.path.join(folder, item)):
            namespaces.append(item)
        elif item != 'index.html':
            files.append(item)

    # We work with relative paths
    paths = get_relative_paths(original_paths, relative_to=folder)

    # Now that everything is setup, write the index.html file
    filename = os.path.join(folder, 'index.html')
    with DocsWriter(filename, type_to_path_function=get_path_for_type) as docs:
        # Title should be the current folder name
        docs.write_head(folder.title(), relative_css_path=paths['css'])

        docs.set_menu_separator(paths['arrow'])
        build_menu(docs, filename, relative_main_index=paths['index_all'])

        docs.write_title(folder.title())

        if namespaces:
            docs.write_title('Namespaces', level=3)
            docs.begin_table(4)
            namespaces.sort()
            for namespace in namespaces:
                # For every namespace, also write the index of it
                generate_index(os.path.join(folder, namespace), original_paths)
                docs.add_row(namespace.title(),
                             link=os.path.join(namespace, 'index.html'))

            docs.end_table()

        docs.write_title('Available items')
        docs.begin_table(2)

        files = [(f, find_title(os.path.join(folder, f))) for f in files]
        files.sort(key=lambda t: t[1])

        for file, title in files:
            docs.add_row(title, link=file)

        docs.end_table()
        docs.end_body()


def get_description(arg):
    """Generates a proper description for the given argument"""
    desc = []
    otherwise = False
    if arg.can_be_inferred:
        desc.append('If left unspecified, it will be inferred automatically.')
        otherwise = True
    elif arg.is_flag:
        desc.append('This argument can be omitted.')
        otherwise = True

    if arg.type in {'InputPeer', 'InputUser', 'InputChannel'}:
        desc.append(
            'Anything entity-like will work if the library can find its '
            '<code>Input</code> version (e.g., usernames, <code>Peer</code>, '
            '<code>User</code> or <code>Channel</code> objects, etc.).'
        )

    if arg.is_vector:
        if arg.is_generic:
            desc.append('A list of other Requests must be supplied.')
        else:
            desc.append('A list must be supplied.')
    elif arg.is_generic:
        desc.append('A different Request must be supplied for this argument.')
    else:
        otherwise = False  # Always reset to false if no other text is added

    if otherwise:
        desc.insert(1, 'Otherwise,')
        desc[-1] = desc[-1][:1].lower() + desc[-1][1:]

    return ' '.join(desc).replace(
        'list',
        '<span class="tooltip" title="Any iterable that supports len() '
        'will work too">list</span>'
    )


def copy_replace(src, dst, replacements):
    """Copies the src file into dst applying the replacements dict"""
    with open(src) as infile, open(dst, 'w') as outfile:
        outfile.write(re.sub(
            '|'.join(re.escape(k) for k in replacements),
            lambda m: str(replacements[m.group(0)]),
            infile.read()
        ))


def generate_documentation(scheme_file):
    """Generates the documentation HTML files from from scheme.tl to
       /methods and /constructors, etc.
    """
    original_paths = {
        'css': 'css/docs.css',
        'arrow': 'img/arrow.svg',
        'search.js': 'js/search.js',
        '404': '404.html',
        'index_all': 'index.html',
        'index_types': 'types/index.html',
        'index_methods': 'methods/index.html',
        'index_constructors': 'constructors/index.html'
    }
    tlobjects = tuple(TLParser.parse_file(scheme_file))

    print('Generating constructors and functions documentation...')

    # Save 'Type: [Constructors]' for use in both:
    # * Seeing the return type or constructors belonging to the same type.
    # * Generating the types documentation, showing available constructors.
    # TODO Tried using 'defaultdict(list)' with strange results, make it work.
    tltypes = {}
    tlfunctions = {}
    for tlobject in tlobjects:
        # Select to which dictionary we want to store this type
        dictionary = tlfunctions if tlobject.is_function else tltypes

        if tlobject.result in dictionary:
            dictionary[tlobject.result].append(tlobject)
        else:
            dictionary[tlobject.result] = [tlobject]

    for tltype, constructors in tltypes.items():
        tltypes[tltype] = list(sorted(constructors, key=lambda c: c.name))

    for tlobject in tlobjects:
        filename = get_create_path_for(tlobject)

        # Determine the relative paths for this file
        paths = get_relative_paths(original_paths, relative_to=filename)

        with DocsWriter(filename, type_to_path_function=get_path_for_type) \
                as docs:
            docs.write_head(
                title=get_class_name(tlobject),
                relative_css_path=paths['css'])

            # Create the menu (path to the current TLObject)
            docs.set_menu_separator(paths['arrow'])
            build_menu(docs, filename, relative_main_index=paths['index_all'])

            # Create the page title
            docs.write_title(get_class_name(tlobject))

            # Write the code definition for this TLObject
            docs.write_code(tlobject)
            docs.write_copy_button('Copy import to the clipboard',
                                   get_import_code(tlobject))

            # Write the return type (or constructors belonging to the same type)
            docs.write_title('Returns' if tlobject.is_function
                             else 'Belongs to', level=3)

            generic_arg = next((arg.name for arg in tlobject.args
                                if arg.generic_definition), None)

            if tlobject.result == generic_arg:
                # We assume it's a function returning a generic type
                generic_arg = next((arg.name for arg in tlobject.args
                                    if arg.is_generic))
                docs.write_text('This function returns the result of whatever '
                                'the result from invoking the request passed '
                                'through <i>{}</i> is.'.format(generic_arg))
            else:
                if re.search('^vector<', tlobject.result, re.IGNORECASE):
                    docs.write_text('A list of the following type is returned.')
                    _, inner = tlobject.result.split('<')
                    inner = inner.strip('>')
                else:
                    inner = tlobject.result

                docs.begin_table(column_count=1)
                docs.add_row(inner, link=get_path_for_type(
                    inner, relative_to=filename
                ))
                docs.end_table()

                constructors = tltypes.get(inner, [])
                if not constructors:
                    docs.write_text('This type has no instances available.')
                elif len(constructors) == 1:
                    docs.write_text('This type can only be an instance of:')
                else:
                    docs.write_text('This type can be an instance of either:')

                docs.begin_table(column_count=2)
                for constructor in constructors:
                    link = get_create_path_for(constructor)
                    link = get_relative_path(link, relative_to=filename)
                    docs.add_row(get_class_name(constructor), link=link)
                docs.end_table()

            # Return (or similar types) written. Now parameters/members
            docs.write_title(
                'Parameters' if tlobject.is_function else 'Members', level=3
            )

            # Sort the arguments in the same way they're sorted
            # on the generated code (flags go last)
            args = [
                a for a in tlobject.sorted_args()
                if not a.flag_indicator and not a.generic_definition
            ]

            if args:
                # Writing parameters
                docs.begin_table(column_count=3)

                for arg in args:
                    # Name row
                    docs.add_row(arg.name,
                                 bold=True)

                    # Type row
                    if arg.is_generic:
                        docs.add_row('!' + arg.type, align='center')
                    else:
                        docs.add_row(
                            arg.type, align='center', link=
                            get_path_for_type(arg.type, relative_to=filename)
                         )

                    # Add a description for this argument
                    docs.add_row(get_description(arg))

                docs.end_table()
            else:
                if tlobject.is_function:
                    docs.write_text('This request takes no input parameters.')
                else:
                    docs.write_text('This type has no members.')

            # TODO Bit hacky, make everything like this? (prepending '../')
            depth = '../' * (2 if tlobject.namespace else 1)
            docs.add_script(src='prependPath = "{}";'.format(depth))
            docs.add_script(relative_src=paths['search.js'])
            docs.end_body()

    # Find all the available types (which are not the same as the constructors)
    # Each type has a list of constructors associated to it, hence is a map
    print('Generating types documentation...')
    for tltype, constructors in tltypes.items():
        filename = get_path_for_type(tltype)
        out_dir = os.path.dirname(filename)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        # Since we don't have access to the full TLObject, split the type
        if '.' in tltype:
            namespace, name = tltype.split('.')
        else:
            namespace, name = None, tltype

        # Determine the relative paths for this file
        paths = get_relative_paths(original_paths, relative_to=out_dir)

        with DocsWriter(filename, type_to_path_function=get_path_for_type) \
                as docs:
            docs.write_head(
                title=get_class_name(name),
                relative_css_path=paths['css'])

            docs.set_menu_separator(paths['arrow'])
            build_menu(docs, filename, relative_main_index=paths['index_all'])

            # Main file title
            docs.write_title(get_class_name(name))

            # List available constructors for this type
            docs.write_title('Available constructors', level=3)
            if not constructors:
                docs.write_text('This type has no constructors available.')
            elif len(constructors) == 1:
                docs.write_text('This type has one constructor available.')
            else:
                docs.write_text('This type has %d constructors available.' %
                                len(constructors))

            docs.begin_table(2)
            for constructor in constructors:
                # Constructor full name
                link = get_create_path_for(constructor)
                link = get_relative_path(link, relative_to=filename)
                docs.add_row(get_class_name(constructor), link=link)
            docs.end_table()

            # List all the methods which return this type
            docs.write_title('Methods returning this type', level=3)
            functions = tlfunctions.get(tltype, [])
            if not functions:
                docs.write_text('No method returns this type.')
            elif len(functions) == 1:
                docs.write_text('Only the following method returns this type.')
            else:
                docs.write_text(
                    'The following %d methods return this type as a result.' %
                    len(functions)
                )

            docs.begin_table(2)
            for func in functions:
                link = get_create_path_for(func)
                link = get_relative_path(link, relative_to=filename)
                docs.add_row(get_class_name(func), link=link)
            docs.end_table()

            # List all the methods which take this type as input
            docs.write_title('Methods accepting this type as input', level=3)
            other_methods = sorted(
                (t for t in tlobjects
                 if any(tltype == a.type for a in t.args) and t.is_function),
                key=lambda t: t.name
            )
            if not other_methods:
                docs.write_text(
                    'No methods accept this type as an input parameter.')
            elif len(other_methods) == 1:
                docs.write_text(
                    'Only this method has a parameter with this type.')
            else:
                docs.write_text(
                    'The following %d methods accept this type as an input '
                    'parameter.' % len(other_methods))

            docs.begin_table(2)
            for ot in other_methods:
                link = get_create_path_for(ot)
                link = get_relative_path(link, relative_to=filename)
                docs.add_row(get_class_name(ot), link=link)
            docs.end_table()

            # List every other type which has this type as a member
            docs.write_title('Other types containing this type', level=3)
            other_types = sorted(
                (t for t in tlobjects
                 if any(tltype == a.type for a in t.args)
                 and not t.is_function
                 ), key=lambda t: t.name
            )

            if not other_types:
                docs.write_text(
                    'No other types have a member of this type.')
            elif len(other_types) == 1:
                docs.write_text(
                    'You can find this type as a member of this other type.')
            else:
                docs.write_text(
                    'You can find this type as a member of any of '
                    'the following %d types.' % len(other_types))

            docs.begin_table(2)
            for ot in other_types:
                link = get_create_path_for(ot)
                link = get_relative_path(link, relative_to=filename)
                docs.add_row(get_class_name(ot), link=link)
            docs.end_table()
            docs.end_body()

    # After everything's been written, generate an index.html per folder.
    # This will be done automatically and not taking into account any extra
    # information that we have available, simply a file listing all the others
    # accessible by clicking on their title
    print('Generating indices...')
    for folder in ['types', 'methods', 'constructors']:
        generate_index(folder, original_paths)

    # Write the final core index, the main index for the rest of files
    layer = TLParser.find_layer(scheme_file)
    types = set()
    methods = []
    constructors = []
    for tlobject in tlobjects:
        if tlobject.is_function:
            methods.append(tlobject)
        else:
            constructors.append(tlobject)

        if not is_core_type(tlobject.result):
            if re.search('^vector<', tlobject.result, re.IGNORECASE):
                types.add(tlobject.result.split('<')[1].strip('>'))
            else:
                types.add(tlobject.result)

    types = sorted(types)
    methods = sorted(methods, key=lambda m: m.name)
    constructors = sorted(constructors, key=lambda c: c.name)

    def fmt(xs):
        ys = {x: get_class_name(x) for x in xs}  # cache TLObject: display
        zs = {}  # create a dict to hold those which have duplicated keys
        for y in ys.values():
            zs[y] = y in zs
        return ', '.join(
            '"{}.{}"'.format(x.namespace, ys[x])
            if zs[ys[x]] and getattr(x, 'namespace', None)
            else '"{}"'.format(ys[x]) for x in xs
        )

    request_names = fmt(methods)
    type_names = fmt(types)
    constructor_names = fmt(constructors)

    def fmt(xs, formatter):
        return ', '.join('"{}"'.format(formatter(x)) for x in xs)

    request_urls = fmt(methods, get_create_path_for)
    type_urls = fmt(types, get_path_for_type)
    constructor_urls = fmt(constructors, get_create_path_for)

    shutil.copy('../res/404.html', original_paths['404'])
    copy_replace('../res/core.html', original_paths['index_all'], {
        '{type_count}': len(types),
        '{method_count}': len(methods),
        '{constructor_count}': len(tlobjects) - len(methods),
        '{layer}': layer,
    })
    os.makedirs(os.path.abspath(os.path.join(
        original_paths['search.js'], os.path.pardir
    )), exist_ok=True)
    copy_replace('../res/js/search.js', original_paths['search.js'], {
        '{request_names}': request_names,
        '{type_names}': type_names,
        '{constructor_names}': constructor_names,
        '{request_urls}': request_urls,
        '{type_urls}': type_urls,
        '{constructor_urls}': constructor_urls
    })

    # Everything done
    print('Documentation generated.')


def copy_resources():
    for d in ('css', 'img'):
        os.makedirs(d, exist_ok=True)

    shutil.copy('../res/img/arrow.svg', 'img')
    shutil.copy('../res/css/docs.css', 'css')


if __name__ == '__main__':
    os.makedirs('generated', exist_ok=True)
    os.chdir('generated')
    try:
        generate_documentation('../../telethon_generator/scheme.tl')
        copy_resources()
    finally:
        os.chdir(os.pardir)
