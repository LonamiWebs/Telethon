import os
import re
import sys

# Small trick so importing telethon_generator works
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from telethon_generator.parser import TLParser, TLObject


# TLObject -> hypertext formatted code
def write_code(file, tlobject, filename):
    """Writes the code for the given 'tlobject' to the 'file' handle with hyperlinks,
       using 'filename' as the file from which the relative links should work"""

    # Write the function or type and its ID
    if tlobject.namespace:
        file.write(tlobject.namespace)
        file.write('.')

    file.write(tlobject.name)
    file.write('#')
    file.write(hex(tlobject.id)[2:].rjust(8, '0'))

    # Write all the arguments (or do nothing if there's none)
    for arg in tlobject.args:
        file.write(' ')

        # "Opening" modifiers
        if arg.generic_definition:
            file.write('{')

        # Argument name
        file.write(arg.name)
        file.write(':')

        # "Opening" modifiers
        if arg.is_flag:
            file.write('flags.%d?' % arg.flag_index)

        if arg.is_generic:
            file.write('!')

        if arg.is_vector:
            file.write('<a href="%s">Vector</a>&lt;' % get_path_for_type('vector', relative_to=filename))

        # Argument type
        if arg.type:
            file.write('<a href="')
            file.write(get_path_for_type(arg.type, relative_to=filename))
            file.write('">%s</a>' % arg.type)
        else:
            file.write('#')

        # "Closing" modifiers
        if arg.is_vector:
            file.write('&gt;')

        if arg.generic_definition:
            file.write('}')

    # Now write the resulting type (result from a function, or type for a constructor)
    file.write(' = <a href="')
    file.write(get_path_for_type(tlobject.result, relative_to=filename))
    file.write('">%s</a>' % tlobject.result)


# TLObject -> Python class name
def get_class_name(tlobject):
    """Gets the class name following the Python style guidelines, in ThisClassFormat"""
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


def get_path_for_type(type, relative_to='.'):
    """Similar to getting the path for a TLObject, it might not be possible
       to have the TLObject itself but rather its name (the type);
       this method works in the same way, returning a relative path"""
    if type.lower() in {'int', 'long', 'int128', 'int256', 'double',
                        'vector', 'string', 'bool', 'true', 'bytes', 'date'}:
        path = 'core/index.html#%s' % type.lower()

    elif '.' in type:
        # If it's not a core type, then it has to be a custom Telegram type
        namespace, name = type.split('.')
        path = 'types/%s/%s' % (namespace, get_file_name(name, add_extension=True))
    else:
        path = 'types/%s' % get_file_name(type, add_extension=True)

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


def generate_documentation(scheme_file):
    """Generates the documentation HTML files from from scheme.tl to /methods and /constructors, etc."""
    original_paths = {
        'css': 'css/docs.css',
        'arrow': 'img/arrow.svg',
        'index_all': 'core/index.html',
        'index_types': 'types/index.html',
        'index_methods': 'methods/index.html',
        'index_constructors': 'constructors/index.html'
    }

    tlobjects = tuple(TLParser.parse_file(scheme_file))

    # First write the functions and the available constructors
    for tlobject in tlobjects:
        filename = get_create_path_for(tlobject)

        # Determine the relative paths for this file
        paths = get_relative_paths(original_paths, relative_to=filename)

        with open(filename, 'w', encoding='utf-8') as file:
            file.write('''<!DOCTYPE html>
<html>
<head>
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
    <title>''')

            # Let the page title be the same as the class name for this object
            file.write(get_class_name(tlobject))

            file.write('''</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link href="''')

            # Use a relative path for the CSS file
            file.write(paths['css'])

            file.write('''" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css?family=Nunito|Space+Mono" rel="stylesheet">
</head>
<body>
<div id="main_div">
    <ul class="horizontal">''')

            # Write the path to the current item
            file.write('<li><a href="')
            file.write(paths['index_all'])
            file.write('">API</a></li>')

            file.write('<img src="%s" />' % paths['arrow'])

            file.write('<li><a href="')
            file.write(paths['index_methods'] if tlobject.is_function else paths['index_constructors'])
            file.write('">')
            file.write('Methods' if tlobject.is_function else 'Constructors')
            file.write('</a></li>')

            file.write('<img src="%s" />' % paths['arrow'])

            if tlobject.namespace:
                file.write('<li><a href="index.html">')
                file.write(tlobject.namespace)
                file.write('</a></li>')
                file.write('<img src="%s" />' % paths['arrow'])

            file.write('<li>%s</li>' % get_file_name(tlobject))

            file.write('</ul><h1>')

            # Body title, again the class name
            file.write(get_class_name(tlobject))

            file.write('</h1>')

            # Is it listed under functions or under types?
            file.write('<pre>---')
            file.write('functions' if tlobject.is_function else 'types')
            file.write('---\n')

            write_code(file, tlobject, filename=filename)

            file.write('</pre>')

            file.write('<h3>')
            file.write('Parameters' if tlobject.is_function else 'Members')
            file.write('</h3>')

            # Sort the arguments in the same way they're sorted on the generated code (flags go last)
            args = sorted([a for a in tlobject.args if
                           not a.flag_indicator and not a.generic_definition],
                          key=lambda a: a.is_flag)
            if args:
                # Writing parameters
                file.write('<table>')

                for arg in args:
                    file.write('<tr>')

                    # Name
                    file.write('<td><b>')
                    file.write(arg.name)
                    file.write('</b></td>')

                    # Type
                    file.write('<td align="center"><a href="')
                    file.write(get_path_for_type(arg.type, relative_to=filename))
                    file.write('">%s</a></td>' % arg.type)

                    # Description
                    file.write('<td>')
                    if arg.is_vector:
                        file.write('A list must be supplied for this argument. ')

                    if arg.is_generic:
                        file.write('A different MTProtoRequest must be supplied for this argument. ')

                    if arg.is_flag:
                        file.write('This argument can be omitted. ')

                    file.write('</td>')
                    file.write('</tr>')

                file.write('</table>')
            else:
                if tlobject.is_function:
                    file.write('<p>This request takes no input parameters.</p>')
                else:
                    file.write('<p>This type has no members.</p>')

            file.write('</div></body></html>')

    # TODO Explain the difference between functions, types and constructors
    # TODO Write index.html for every sub-folder (functions/, types/ and constructors/) as well as sub-namespaces
    # TODO Write the core/index.html containing the core types
    #
    # Find all the available types (which are not the same as the constructors)
    # Each type has a list of constructors associated to it, so it should be a map
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
        filename = get_path_for_type(tltype)
        out_dir = os.path.dirname(filename)
        os.makedirs(out_dir, exist_ok=True)

        # Since we don't have access to the full TLObject, split the type into namespace.name
        if '.' in tltype:
            namespace, name = tltype.split('.')
        else:
            namespace, name = None, tltype

        # Determine the relative paths for this file
        paths = get_relative_paths(original_paths, relative_to=out_dir)

        with open(filename, 'w', encoding='utf-8') as file:
            file.write('''<!DOCTYPE html>
        <html>
        <head>
            <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
            <title>''')

            # Let the page title be the same as the class name for this TL type (using its name)
            file.write(get_class_name(name))

            file.write('''</title>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <link href="''')

            # Use a relative path for the CSS file
            file.write(paths['css'])

            file.write('''" rel="stylesheet">
            <link href="https://fonts.googleapis.com/css?family=Nunito|Space+Mono" rel="stylesheet">
        </head>
        <body>
        <div id="main_div">
            <ul class="horizontal">''')

            # Write the path to the current item
            file.write('<li><a href="')
            file.write(paths['index_all'])
            file.write('">API</a></li>')

            file.write('<img src="%s" />' % paths['arrow'])

            file.write('<li><a href="%s">Types</a></li>' % paths['index_types'])

            file.write('<img src="%s" />' % paths['arrow'])

            if namespace:
                file.write('<li><a href="index.html">')
                file.write(namespace)
                file.write('</a></li>')
                file.write('<img src="%s" />' % paths['arrow'])

            file.write('<li>%s</li>' % get_file_name(name))

            file.write('</ul><h1>')

            # Body title, again the class name
            file.write(get_class_name(name))

            # Write all the available constructors for this abstract type
            file.write('</h1><h3>Available constructors</h3><p>')

            if not constructors:
                file.write('This type has no constructors available.')
            elif len(constructors) == 1:
                file.write('This type has one constructor available.')
            else:
                file.write('This type has %d constructors available.' % len(constructors))

            file.write('</p><table>')
            for constructor in constructors:
                file.write('<tr>')

                # Constructor full name
                link = get_create_path_for(constructor)
                link = get_relative_path(link, relative_to=filename)

                file.write('<td align="center"><a href="%s">' % link)
                file.write(get_class_name(constructor))
                file.write('</a></td>')

                # Description
                file.write('<td></td>')
                file.write('</tr>')

            file.write('</table>')

            # Write all the functions which return this abstract type
            file.write('<h3>Methods returning this type</h3><p>')
            functions = tlfunctions.get(tltype, [])

            if not functions:
                file.write('No method returns this type.')
            elif len(functions) == 1:
                file.write('Only the following method returns this type.')
            else:
                file.write('The following %d methods return this type as a result.' % len(functions))

            file.write('</p><table>')
            for function in functions:
                file.write('<tr>')

                # Constructor full name
                link = get_create_path_for(function)
                link = get_relative_path(link, relative_to=filename)

                file.write('<td align="center"><a href="%s">' % link)
                file.write(get_class_name(function))
                file.write('</a></td>')

                # Description
                file.write('<td></td>')
                file.write('</tr>')

            file.write('</table>')
            file.write('</div></body></html>')

    # Done, written all functions, constructors and types


if __name__ == '__main__':
    print('Generating documentation...')
    generate_documentation('../telethon_generator/scheme.tl')
    print('Done.')
