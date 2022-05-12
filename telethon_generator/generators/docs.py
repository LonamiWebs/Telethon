#!/usr/bin/env python3
import functools
import os
import pathlib
import re
import shutil
from collections import defaultdict
from pathlib import Path

from ..docswriter import DocsWriter
from ..parsers import TLObject, Usability
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


def _get_path_for(tlobject):
    """Returns the path for the given TLObject."""
    out_dir = pathlib.Path('methods' if tlobject.is_function else 'constructors')
    if tlobject.namespace:
        out_dir /= tlobject.namespace

    return out_dir / _get_file_name(tlobject)


def _get_path_for_type(type_):
    """Similar to `_get_path_for` but for only type names."""
    if type_.lower() in CORE_TYPES:
        return Path('index.html#%s' % type_.lower())
    elif '.' in type_:
        namespace, name = type_.split('.')
        return Path('types', namespace, _get_file_name(name))
    else:
        return Path('types',  _get_file_name(type_))


def _find_title(html_file):
    """Finds the <title> for the given HTML file, or (Unknown)."""
    # TODO Is it necessary to read files like this?
    with html_file.open() as f:
        for line in f:
            if '<title>' in line:
                # + 7 to skip len('<title>')
                return line[line.index('<title>') + 7:line.index('</title>')]

    return '(Unknown)'


def _build_menu(docs):
    """
    Builds the menu used for the current ``DocumentWriter``.
    """

    paths = []
    current = docs.filename
    top = pathlib.Path('.')
    while current != top:
        current = current.parent
        paths.append(current)

    for path in reversed(paths):
        docs.add_menu(path.stem.title() or 'API', link=path / 'index.html')

    if docs.filename.stem != 'index':
        docs.add_menu(docs.title, link=docs.filename)

    docs.end_menu()


def _generate_index(folder, paths,
                    bots_index=False, bots_index_paths=()):
    """Generates the index file for the specified folder"""
    # Determine the namespaces listed here (as sub folders)
    # and the files (.html files) that we should link to
    namespaces = []
    files = []
    INDEX = 'index.html'
    BOT_INDEX = 'botindex.html'

    for item in (bots_index_paths or folder.iterdir()):
        if item.is_dir():
            namespaces.append(item)
        elif item.name not in (INDEX, BOT_INDEX):
            files.append(item)

    # Now that everything is setup, write the index.html file
    filename = folder / (BOT_INDEX if bots_index else INDEX)
    with DocsWriter(filename, _get_path_for_type) as docs:
        # Title should be the current folder name
        docs.write_head(str(folder).replace(os.path.sep, '/').title(),
                        css_path=paths['css'],
                        default_css=paths['default_css'])

        docs.set_menu_separator(paths['arrow'])
        _build_menu(docs)
        docs.write_title(str(filename.parent)
                         .replace(os.path.sep, '/').title())

        if bots_index:
            docs.write_text('These are the methods that you may be able to '
                            'use as a bot. Click <a href="{}">here</a> to '
                            'view them all.'.format(INDEX))
        else:
            docs.write_text('Click <a href="{}">here</a> to view the methods '
                            'that you can use as a bot.'.format(BOT_INDEX))
        if namespaces:
            docs.write_title('Namespaces', level=3)
            docs.begin_table(4)
            namespaces.sort()
            for namespace in namespaces:
                # For every namespace, also write the index of it
                namespace_paths = []
                if bots_index:
                    for item in bots_index_paths:
                        if item.parent == namespace:
                            namespace_paths.append(item)

                _generate_index(namespace, paths,
                                bots_index, namespace_paths)

                docs.add_row(
                    namespace.stem.title(),
                    link=namespace / (BOT_INDEX if bots_index else INDEX))

            docs.end_table()

        docs.write_title('Available items')
        docs.begin_table(2)

        files = [(f, _find_title(f)) for f in files]
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
    elif arg.flag:
        desc.append('This argument defaults to '
                    '<code>None</code> and can be omitted.')
        otherwise = True

    if arg.type in {'InputPeer', 'InputUser', 'InputChannel',
                    'InputNotifyPeer', 'InputDialogPeer'}:
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
    with src.open() as infile, dst.open('w') as outfile:
        outfile.write(re.sub(
            '|'.join(re.escape(k) for k in replacements),
            lambda m: str(replacements[m.group(0)]),
            infile.read()
        ))


def _write_html_pages(tlobjects, methods, layer, input_res):
    """
    Generates the documentation HTML files from from ``scheme.tl``
    to ``/methods`` and ``/constructors``, etc.
    """
    # Save 'Type: [Constructors]' for use in both:
    # * Seeing the return type or constructors belonging to the same type.
    # * Generating the types documentation, showing available constructors.
    paths = {k: pathlib.Path(v) for k, v in (
        ('css', 'css'),
        ('arrow', 'img/arrow.svg'),
        ('search.js', 'js/search.js'),
        ('404', '404.html'),
        ('index_all', 'index.html'),
        ('bot_index', 'botindex.html'),
        ('index_types', 'types/index.html'),
        ('index_methods', 'methods/index.html'),
        ('index_constructors', 'constructors/index.html')
    )}
    paths['default_css'] = 'light'  # docs.<name>.css, local path
    type_to_constructors = defaultdict(list)
    type_to_functions = defaultdict(list)
    for tlobject in tlobjects:
        d = type_to_functions if tlobject.is_function else type_to_constructors
        d[tlobject.innermost_result].append(tlobject)

    for t, cs in type_to_constructors.items():
        type_to_constructors[t] = list(sorted(cs, key=lambda c: c.name))

    methods = {m.name: m for m in methods}
    bot_docs_paths = []

    for tlobject in tlobjects:
        filename = _get_path_for(tlobject)
        with DocsWriter(filename, _get_path_for_type) as docs:
            docs.write_head(title=tlobject.class_name,
                            css_path=paths['css'],
                            default_css=paths['default_css'])

            # Create the menu (path to the current TLObject)
            docs.set_menu_separator(paths['arrow'])
            _build_menu(docs)

            # Create the page title
            docs.write_title(tlobject.class_name)

            if tlobject.is_function:
                if tlobject.usability == Usability.USER:
                    start = '<strong>Only users</strong> can'
                elif tlobject.usability == Usability.BOT:
                    bot_docs_paths.append(filename)
                    start = '<strong>Only bots</strong> can'
                elif tlobject.usability == Usability.BOTH:
                    bot_docs_paths.append(filename)
                    start = '<strong>Both users and bots</strong> can'
                else:
                    bot_docs_paths.append(filename)
                    start = \
                        'Both users and bots <strong>may</strong> be able to'

                docs.write_text('{} use this method. <a href="#examples">'
                                'See code examples.</a>'.format(start))

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
                    inner = tlobject.innermost_result
                else:
                    inner = tlobject.result

                docs.begin_table(column_count=1)
                docs.add_row(inner, link=_get_path_for_type(inner))
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
                    link = _get_path_for(constructor)
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
                    friendly_type = 'flag' if arg.type == 'true' else arg.type
                    if arg.is_generic:
                        docs.add_row('!' + friendly_type, align='center')
                    else:
                        docs.add_row(
                            friendly_type, align='center',
                            link=_get_path_for_type(arg.type)
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
                method_info = methods.get(tlobject.fullname)
                errors = method_info and method_info.errors
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

                docs.write_title('Example', id='examples')
                if tlobject.friendly:
                    ns, friendly = tlobject.friendly
                    docs.write_text(
                        'Please refer to the documentation of <a href="'
                        'https://docs.telethon.dev/en/latest/modules/client.html'
                        '#telethon.client.{0}.{1}"><code>client.{1}()</code></a> '
                        'to learn about the parameters and see several code '
                        'examples on how to use it.'
                        .format(ns, friendly)
                    )
                    docs.write_text(
                        'The method above is the recommended way to do it. '
                        'If you need more control over the parameters or want '
                        'to learn how it is implemented, open the details by '
                        'clicking on the "Details" text.'
                    )
                    docs.write('<details>')

                docs.write('''<pre>\
<strong>from</strong> telethon.sync <strong>import</strong> TelegramClient
<strong>from</strong> telethon <strong>import</strong> functions, types

<strong>with</strong> TelegramClient(name, api_id, api_hash) <strong>as</strong> client:
    result = client(''')
                tlobject.as_example(docs, indent=1)
                docs.write(')\n')
                if tlobject.result.startswith('Vector'):
                    docs.write('''\
    <strong>for</strong> x <strong>in</strong> result:
        print(x''')
                else:
                    docs.write('    print(result')
                    if tlobject.result != 'Bool' \
                            and not tlobject.result.startswith('Vector'):
                        docs.write('.stringify()')

                docs.write(')</pre>')
                if tlobject.friendly:
                    docs.write('</details>')

            depth = '../' * (2 if tlobject.namespace else 1)
            docs.add_script(src='prependPath = "{}";'.format(depth))
            docs.add_script(path=paths['search.js'])
            docs.end_body()

    # Find all the available types (which are not the same as the constructors)
    # Each type has a list of constructors associated to it, hence is a map
    for t, cs in type_to_constructors.items():
        filename = _get_path_for_type(t)
        out_dir = filename.parent
        if out_dir:
            out_dir.mkdir(parents=True, exist_ok=True)

        # Since we don't have access to the full TLObject, split the type
        if '.' in t:
            namespace, name = t.split('.')
        else:
            namespace, name = None, t

        with DocsWriter(filename, _get_path_for_type) as docs:
            docs.write_head(title=snake_to_camel_case(name),
                            css_path=paths['css'],
                            default_css=paths['default_css'])

            docs.set_menu_separator(paths['arrow'])
            _build_menu(docs)

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
                link = _get_path_for(constructor)
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
                link = _get_path_for(func)
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
                link = _get_path_for(ot)
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
                link = _get_path_for(ot)
                docs.add_row(ot.class_name, link=link)
            docs.end_table()
            docs.end_body()

    # After everything's been written, generate an index.html per folder.
    # This will be done automatically and not taking into account any extra
    # information that we have available, simply a file listing all the others
    # accessible by clicking on their title
    for folder in ['types', 'methods', 'constructors']:
        _generate_index(pathlib.Path(folder), paths)

    _generate_index(pathlib.Path('methods'), paths, True,
                    bot_docs_paths)

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
                types.add(tlobject.innermost_result)
            else:
                types.add(tlobject.result)

    types = sorted(types)
    methods = sorted(methods, key=lambda m: m.name)
    cs = sorted(cs, key=lambda c: c.name)

    shutil.copy(str(input_res / '404.html'), str(paths['404']))
    _copy_replace(input_res / 'core.html', paths['index_all'], {
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
        return ', '.join('"{}"'.format(
            formatter(x)).replace(os.path.sep, '/') for x in xs)

    type_names = fmt(types, formatter=lambda x: x)

    request_urls = fmt(methods, _get_path_for)
    type_urls = fmt(types, _get_path_for_type)
    constructor_urls = fmt(cs, _get_path_for)

    paths['search.js'].parent.mkdir(parents=True, exist_ok=True)
    _copy_replace(input_res / 'js/search.js', paths['search.js'], {
        '{request_names}': request_names,
        '{type_names}': type_names,
        '{constructor_names}': constructor_names,
        '{request_urls}': request_urls,
        '{type_urls}': type_urls,
        '{constructor_urls}': constructor_urls
    })


def _copy_resources(res_dir):
    for dirname, files in [('css', ['docs.light.css', 'docs.dark.css']),
                           ('img', ['arrow.svg'])]:
        dirpath = pathlib.Path(dirname)
        dirpath.mkdir(parents=True, exist_ok=True)
        for file in files:
            shutil.copy(str(res_dir / dirname / file), str(dirpath))


def _create_structure(tlobjects):
    """
    Pre-create the required directory structure.
    """
    types_ns = set()
    method_ns = set()
    for obj in tlobjects:
        if obj.namespace:
            if obj.is_function:
                method_ns.add(obj.namespace)
            else:
                types_ns.add(obj.namespace)

    output_dir = pathlib.Path('.')
    type_dir = output_dir / 'types'
    type_dir.mkdir(exist_ok=True)

    cons_dir = output_dir / 'constructors'
    cons_dir.mkdir(exist_ok=True)
    for ns in types_ns:
        (type_dir / ns).mkdir(exist_ok=True)
        (cons_dir / ns).mkdir(exist_ok=True)

    meth_dir = output_dir / 'methods'
    meth_dir.mkdir(exist_ok=True)
    for ns in types_ns:
        (meth_dir / ns).mkdir(exist_ok=True)


def generate_docs(tlobjects, methods_info, layer, input_res):
    _create_structure(tlobjects)
    _write_html_pages(tlobjects, methods_info, layer, input_res)
    _copy_resources(input_res)
