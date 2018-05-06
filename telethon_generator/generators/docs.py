#!/usr/bin/env python3
import functools
import os
import re
import shutil
from collections import defaultdict

from ..docs_writer import DocsWriter
from ..parsers import TLObject
from ..utils import snake_to_camel_case


CORE_TYPES = {
    'int', 'long', 'int128', 'int256', 'double',
    'vector', 'string', 'bool', 'true', 'bytes', 'date'
}


def _get_file_name(tlobject):
    """``ClassName -> class_name.html``."""
    name = tlobject.name if isinstance(tlobject, TLObject) else tlobject
    # Courtesy of http://stackoverflow.com/a/1176023/4759433
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    result = re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
    return '{}.html'.format(result)


def get_import_code(tlobject):
    """``TLObject -> from ... import ...``."""
    kind = 'functions' if tlobject.is_function else 'types'
    ns = '.' + tlobject.namespace if tlobject.namespace else ''
    return 'from telethon.tl.{}{} import {}'\
        .format(kind, ns, tlobject.class_name)


def _get_create_path_for(root, tlobject):
    """Creates and returns the path for the given TLObject at root."""
    out_dir = 'methods' if tlobject.is_function else 'constructors'
    if tlobject.namespace:
        out_dir = os.path.join(out_dir, tlobject.namespace)

    out_dir = os.path.join(root, out_dir)
    os.makedirs(out_dir, exist_ok=True)
    return os.path.join(out_dir, _get_file_name(tlobject))


def _get_path_for_type(root, type_, relative_to='.'):
    """Similar to `_get_create_path_for` but for only type names."""
    if type_.lower() in CORE_TYPES:
        path = 'index.html#%s' % type_.lower()
    elif '.' in type_:
        namespace, name = type_.split('.')
        path = 'types/%s/%s' % (namespace, _get_file_name(name))
    else:
        path = 'types/%s' % _get_file_name(type_)

    return _get_relative_path(os.path.join(root, path), relative_to)


def _get_relative_path(destination, relative_to, folder=False):
    """Return the relative path to destination from relative_to."""
    if not folder:
        relative_to = os.path.dirname(relative_to)

    return os.path.relpath(destination, start=relative_to)


def _find_title(html_file):
    """Finds the <title> for the given HTML file, or (Unknown)."""
    with open(html_file) as fp:
        for line in fp:
            if '<title>' in line:
                # + 7 to skip len('<title>')
                return line[line.index('<title>') + 7:line.index('</title>')]

    return '(Unknown)'


def _build_menu(docs, filename, root, relative_main_index):
    """Builds the menu using the given DocumentWriter up to 'filename',
       which must be a file (it cannot be a directory)"""
    # TODO Maybe this could be part of DocsWriter itself, "build path menu"
    filename = _get_relative_path(filename, root)
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


def _generate_index(folder, original_paths, root):
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

    paths = {k: _get_relative_path(v, folder, folder=True)
             for k, v in original_paths.items()}

    # Now that everything is setup, write the index.html file
    filename = os.path.join(folder, 'index.html')
    with DocsWriter(filename, type_to_path=_get_path_for_type) as docs:
        # Title should be the current folder name
        docs.write_head(folder.title(), relative_css_path=paths['css'])

        docs.set_menu_separator(paths['arrow'])
        _build_menu(docs, filename, root,
                    relative_main_index=paths['index_all'])

        docs.write_title(_get_relative_path(folder, root, folder=True).title())
        if namespaces:
            docs.write_title('Namespaces', level=3)
            docs.begin_table(4)
            namespaces.sort()
            for namespace in namespaces:
                # For every namespace, also write the index of it
                _generate_index(os.path.join(folder, namespace),
                                original_paths, root)
                docs.add_row(namespace.title(),
                             link=os.path.join(namespace, 'index.html'))

            docs.end_table()

        docs.write_title('Available items')
        docs.begin_table(2)

        files = [(f, _find_title(os.path.join(folder, f))) for f in files]
        files.sort(key=lambda t: t[1])

        for file, title in files:
            docs.add_row(title, link=file)

        docs.end_table()
        docs.end_body()


def _get_description(arg):
    """Generates a proper description for the given argument."""
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


def _copy_replace(src, dst, replacements):
    """Copies the src file into dst applying the replacements dict"""
    with open(src) as infile, open(dst, 'w') as outfile:
        outfile.write(re.sub(
            '|'.join(re.escape(k) for k in replacements),
            lambda m: str(replacements[m.group(0)]),
            infile.read()
        ))


def _write_html_pages(tlobjects, errors, layer, input_res, output_dir):
    """
    Generates the documentation HTML files from from ``scheme.tl``
    to ``/methods`` and ``/constructors``, etc.
    """
    # Save 'Type: [Constructors]' for use in both:
    # * Seeing the return type or constructors belonging to the same type.
    # * Generating the types documentation, showing available constructors.
    # TODO Tried using 'defaultdict(list)' with strange results, make it work.
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
    original_paths = {k: os.path.join(output_dir, v)
                      for k, v in original_paths.items()}

    type_to_constructors = {}
    type_to_functions = {}
    for tlobject in tlobjects:
        d = type_to_functions if tlobject.is_function else type_to_constructors
        if tlobject.result in d:
            d[tlobject.result].append(tlobject)
        else:
            d[tlobject.result] = [tlobject]

    for t, cs in type_to_constructors.items():
        type_to_constructors[t] = list(sorted(cs, key=lambda c: c.name))

    # Telegram may send errors with the same str_code but different int_code.
    # They are all imported on telethon.errors anyway so makes no difference.
    errors = list(sorted({e.str_code: e for e in errors}.values(),
                         key=lambda e: e.name))

    method_causes_errors = defaultdict(list)
    for error in errors:
        for method in error.caused_by:
            method_causes_errors[method].append(error)

    # Since the output directory is needed everywhere partially apply it now
    create_path_for = functools.partial(_get_create_path_for, output_dir)
    path_for_type = functools.partial(_get_path_for_type, output_dir)

    for tlobject in tlobjects:
        filename = create_path_for(tlobject)
        paths = {k: _get_relative_path(v, filename)
                 for k, v in original_paths.items()}

        with DocsWriter(filename, type_to_path=path_for_type) as docs:
            docs.write_head(title=tlobject.class_name,
                            relative_css_path=paths['css'])

            # Create the menu (path to the current TLObject)
            docs.set_menu_separator(paths['arrow'])
            _build_menu(docs, filename, output_dir,
                        relative_main_index=paths['index_all'])

            # Create the page title
            docs.write_title(tlobject.class_name)

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
                docs.add_row(inner, link=path_for_type(
                    inner, relative_to=filename
                ))
                docs.end_table()

                cs = type_to_constructors.get(inner, [])
                if not cs:
                    docs.write_text('This type has no instances available.')
                elif len(cs) == 1:
                    docs.write_text('This type can only be an instance of:')
                else:
                    docs.write_text('This type can be an instance of either:')

                docs.begin_table(column_count=2)
                for constructor in cs:
                    link = create_path_for(constructor)
                    link = _get_relative_path(link, relative_to=filename)
                    docs.add_row(constructor.class_name, link=link)
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
                            path_for_type(arg.type, relative_to=filename)
                         )

                    # Add a description for this argument
                    docs.add_row(_get_description(arg))

                docs.end_table()
            else:
                if tlobject.is_function:
                    docs.write_text('This request takes no input parameters.')
                else:
                    docs.write_text('This type has no members.')

            if tlobject.is_function:
                docs.write_title('Known RPC errors')
                errors = method_causes_errors[tlobject.fullname]
                if not errors:
                    docs.write_text("This request can't cause any RPC error "
                                    "as far as we know.")
                else:
                    docs.write_text(
                        'This request can cause {} known error{}:'.format(
                            len(errors), '' if len(errors) == 1 else 's'
                    ))
                    docs.begin_table(column_count=2)
                    for error in errors:
                        docs.add_row('<code>{}</code>'.format(error.name))
                        docs.add_row('{}.'.format(error.description))
                    docs.end_table()
                    docs.write_text('You can import these from '
                                    '<code>telethon.errors</code>.')

            # TODO Bit hacky, make everything like this? (prepending '../')
            depth = '../' * (2 if tlobject.namespace else 1)
            docs.add_script(src='prependPath = "{}";'.format(depth))
            docs.add_script(relative_src=paths['search.js'])
            docs.end_body()

    # Find all the available types (which are not the same as the constructors)
    # Each type has a list of constructors associated to it, hence is a map
    for t, cs in type_to_constructors.items():
        filename = path_for_type(t)
        out_dir = os.path.dirname(filename)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        # Since we don't have access to the full TLObject, split the type
        if '.' in t:
            namespace, name = t.split('.')
        else:
            namespace, name = None, t

        paths = {k: _get_relative_path(v, out_dir, folder=True)
                 for k, v in original_paths.items()}

        with DocsWriter(filename, type_to_path=path_for_type) as docs:
            docs.write_head(
                title=snake_to_camel_case(name),
                relative_css_path=paths['css'])

            docs.set_menu_separator(paths['arrow'])
            _build_menu(docs, filename, output_dir,
                        relative_main_index=paths['index_all'])

            # Main file title
            docs.write_title(snake_to_camel_case(name))

            # List available constructors for this type
            docs.write_title('Available constructors', level=3)
            if not cs:
                docs.write_text('This type has no constructors available.')
            elif len(cs) == 1:
                docs.write_text('This type has one constructor available.')
            else:
                docs.write_text('This type has %d constructors available.' %
                                len(cs))

            docs.begin_table(2)
            for constructor in cs:
                # Constructor full name
                link = create_path_for(constructor)
                link = _get_relative_path(link, relative_to=filename)
                docs.add_row(constructor.class_name, link=link)
            docs.end_table()

            # List all the methods which return this type
            docs.write_title('Methods returning this type', level=3)
            functions = type_to_functions.get(t, [])
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
                link = create_path_for(func)
                link = _get_relative_path(link, relative_to=filename)
                docs.add_row(func.class_name, link=link)
            docs.end_table()

            # List all the methods which take this type as input
            docs.write_title('Methods accepting this type as input', level=3)
            other_methods = sorted(
                (u for u in tlobjects
                 if any(a.type == t for a in u.args) and u.is_function),
                key=lambda u: u.name
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
                link = create_path_for(ot)
                link = _get_relative_path(link, relative_to=filename)
                docs.add_row(ot.class_name, link=link)
            docs.end_table()

            # List every other type which has this type as a member
            docs.write_title('Other types containing this type', level=3)
            other_types = sorted(
                (u for u in tlobjects
                 if any(a.type == t for a in u.args) and not u.is_function),
                key=lambda u: u.name
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
                link = create_path_for(ot)
                link = _get_relative_path(link, relative_to=filename)
                docs.add_row(ot.class_name, link=link)
            docs.end_table()
            docs.end_body()

    # After everything's been written, generate an index.html per folder.
    # This will be done automatically and not taking into account any extra
    # information that we have available, simply a file listing all the others
    # accessible by clicking on their title
    for folder in ['types', 'methods', 'constructors']:
        _generate_index(os.path.join(output_dir, folder), original_paths,
                        output_dir)

    # Write the final core index, the main index for the rest of files
    types = set()
    methods = []
    cs = []
    for tlobject in tlobjects:
        if tlobject.is_function:
            methods.append(tlobject)
        else:
            cs.append(tlobject)

        if not tlobject.result.lower() in CORE_TYPES:
            if re.search('^vector<', tlobject.result, re.IGNORECASE):
                types.add(tlobject.result.split('<')[1].strip('>'))
            else:
                types.add(tlobject.result)

    types = sorted(types)
    methods = sorted(methods, key=lambda m: m.name)
    cs = sorted(cs, key=lambda c: c.name)

    shutil.copy(os.path.join(input_res, '404.html'), original_paths['404'])
    _copy_replace(os.path.join(input_res, 'core.html'),
                  original_paths['index_all'], {
        '{type_count}': len(types),
        '{method_count}': len(methods),
        '{constructor_count}': len(tlobjects) - len(methods),
        '{layer}': layer,
    })

    def fmt(xs):
        zs = {}  # create a dict to hold those which have duplicated keys
        for x in xs:
            zs[x.class_name] = x.class_name in zs
        return ', '.join(
            '"{}.{}"'.format(x.namespace, x.class_name)
            if zs[x.class_name] and x.namespace
            else '"{}"'.format(x.class_name) for x in xs
        )

    request_names = fmt(methods)
    constructor_names = fmt(cs)

    def fmt(xs, formatter):
        return ', '.join('"{}"'.format(formatter(x)) for x in xs)

    type_names = fmt(types, formatter=lambda x: x)

    # Local URLs shouldn't rely on the output's root, so set empty root
    create_path_for = functools.partial(_get_create_path_for, '')
    path_for_type = functools.partial(_get_path_for_type, '')
    request_urls = fmt(methods, create_path_for)
    type_urls = fmt(types, path_for_type)
    constructor_urls = fmt(cs, create_path_for)

    os.makedirs(os.path.abspath(os.path.join(
        original_paths['search.js'], os.path.pardir
    )), exist_ok=True)
    _copy_replace(os.path.join(input_res, 'js', 'search.js'),
                  original_paths['search.js'], {
        '{request_names}': request_names,
        '{type_names}': type_names,
        '{constructor_names}': constructor_names,
        '{request_urls}': request_urls,
        '{type_urls}': type_urls,
        '{constructor_urls}': constructor_urls
    })


def _copy_resources(res_dir, out_dir):
    for dirname, files in [('css', ['docs.css']), ('img', ['arrow.svg'])]:
        dirpath = os.path.join(out_dir, dirname)
        os.makedirs(dirpath, exist_ok=True)
        for file in files:
            shutil.copy(os.path.join(res_dir, dirname, file), dirpath)


def generate_docs(tlobjects, errors, layer, input_res, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    _write_html_pages(tlobjects, errors, layer, input_res, output_dir)
    _copy_resources(input_res, output_dir)
