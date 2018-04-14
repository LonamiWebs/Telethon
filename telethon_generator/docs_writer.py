import os
import re


class DocsWriter:
    """Utility class used to write the HTML files used on the documentation"""
    def __init__(self, filename, type_to_path_function):
        """Initializes the writer to the specified output file,
           creating the parent directories when used if required.

           'type_to_path_function' should be a function which, given a type
           name and a named argument relative_to, returns the file path for
           the specified type, relative to the given filename
        """
        self.filename = filename
        self.handle = None

        # Should be set before calling adding items to the menu
        self.menu_separator_tag = None

        # Utility functions TODO There must be a better way
        self.type_to_path = lambda t: type_to_path_function(
            t, relative_to=self.filename
        )

        # Control signals
        self.menu_began = False
        self.table_columns = 0
        self.table_columns_left = None
        self.write_copy_script = False
        self._script = ''

    # High level writing
    def write_head(self, title, relative_css_path):
        """Writes the head part for the generated document,
           with the given title and CSS
        """
        self.write('''<!DOCTYPE html>
<html>
<head>
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
    <title>''')

        self.write(title)

        self.write('''</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link href="''')

        self.write(relative_css_path)

        self.write('''" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css?family=Nunito|Source+Code+Pro" rel="stylesheet">
</head>
<body>
<div id="main_div">''')

    def set_menu_separator(self, relative_image_path):
        """Sets the menu separator.
           Must be called before adding entries to the menu
        """
        if relative_image_path:
            self.menu_separator_tag = \
                '<img src="{}" alt="/" />'.format(relative_image_path)
        else:
            self.menu_separator_tag = None

    def add_menu(self, name, link=None):
        """Adds a menu entry, will create it if it doesn't exist yet"""
        if self.menu_began:
            if self.menu_separator_tag:
                self.write(self.menu_separator_tag)
        else:
            # First time, create the menu tag
            self.write('<ul class="horizontal">')
            self.menu_began = True

        self.write('<li>')
        if link:
            self.write('<a href="')
            self.write(link)
            self.write('">')

        # Write the real menu entry text
        self.write(name)

        if link:
            self.write('</a>')
        self.write('</li>')

    def end_menu(self):
        """Ends an opened menu"""
        if not self.menu_began:
            raise RuntimeError('No menu had been started in the first place.')
        self.write('</ul>')

    def write_title(self, title, level=1):
        """Writes a title header in the document body,
           with an optional depth level
        """
        self.write('<h%d>' % level)
        self.write(title)
        self.write('</h%d>' % level)

    def write_code(self, tlobject):
        """Writes the code for the given 'tlobject' properly
           formatted with hyperlinks
        """
        self.write('<pre>---')
        self.write('functions' if tlobject.is_function else 'types')
        self.write('---\n')

        # Write the function or type and its ID
        if tlobject.namespace:
            self.write(tlobject.namespace)
            self.write('.')

        self.write(tlobject.name)
        self.write('#')
        self.write(hex(tlobject.id)[2:].rjust(8, '0'))

        # Write all the arguments (or do nothing if there's none)
        for arg in tlobject.args:
            self.write(' ')
            add_link = not arg.generic_definition and not arg.is_generic

            # "Opening" modifiers
            if arg.generic_definition:
                self.write('{')

            # Argument name
            self.write(arg.name)
            self.write(':')

            # "Opening" modifiers
            if arg.is_flag:
                self.write('flags.%d?' % arg.flag_index)

            if arg.is_generic:
                self.write('!')

            if arg.is_vector:
                self.write(
                    '<a href="%s">Vector</a>&lt;' % self.type_to_path('vector')
                )

            # Argument type
            if arg.type:
                if add_link:
                    self.write('<a href="%s">' % self.type_to_path(arg.type))
                self.write(arg.type)
                if add_link:
                    self.write('</a>')
            else:
                self.write('#')

            # "Closing" modifiers
            if arg.is_vector:
                self.write('&gt;')

            if arg.generic_definition:
                self.write('}')

        # Now write the resulting type (result from a function/type)
        self.write(' = ')
        generic_name = next((arg.name for arg in tlobject.args
                             if arg.generic_definition), None)

        if tlobject.result == generic_name:
            # Generic results cannot have any link
            self.write(tlobject.result)
        else:
            if re.search('^vector<', tlobject.result, re.IGNORECASE):
                # Notice that we don't simply make up the "Vector" part,
                # because some requests (as of now, only FutureSalts),
                # use a lower type name for it (see #81)
                vector, inner = tlobject.result.split('<')
                inner = inner.strip('>')
                self.write('<a href="')
                self.write(self.type_to_path(vector))
                self.write('">%s</a>&lt;' % vector)

                self.write('<a href="')
                self.write(self.type_to_path(inner))
                self.write('">%s</a>' % inner)

                self.write('&gt;')
            else:
                self.write('<a href="')
                self.write(self.type_to_path(tlobject.result))
                self.write('">%s</a>' % tlobject.result)

        self.write('</pre>')

    def begin_table(self, column_count):
        """Begins a table with the given 'column_count', required to automatically
           create the right amount of columns when adding items to the rows"""
        self.table_columns = column_count
        self.table_columns_left = 0
        self.write('<table>')

    def add_row(self, text, link=None, bold=False, align=None):
        """This will create a new row, or add text to the next column
           of the previously created, incomplete row, closing it if complete"""
        if not self.table_columns_left:
            # Starting a new row
            self.write('<tr>')
            self.table_columns_left = self.table_columns

        self.write('<td')
        if align:
            self.write(' style="text-align:')
            self.write(align)
            self.write('"')
        self.write('>')

        if bold:
            self.write('<b>')
        if link:
            self.write('<a href="')
            self.write(link)
            self.write('">')

        # Finally write the real table data, the given text
        self.write(text)

        if link:
            self.write('</a>')
        if bold:
            self.write('</b>')

        self.write('</td>')

        self.table_columns_left -= 1
        if not self.table_columns_left:
            self.write('</tr>')

    def end_table(self):
        # If there was any column left, finish it before closing the table
        if self.table_columns_left:
            self.write('</tr>')

        self.write('</table>')

    def write_text(self, text):
        """Writes a paragraph of text"""
        self.write('<p>')
        self.write(text)
        self.write('</p>')

    def write_copy_button(self, text, text_to_copy):
        """Writes a button with 'text' which can be used
           to copy 'text_to_copy' to clipboard when it's clicked."""
        self.write_copy_script = True
        self.write('<button onclick="cp(\'{}\');">{}</button>'
                   .format(text_to_copy, text))

    def add_script(self, src='', relative_src=None):
        if relative_src:
            self._script += '<script src="{}"></script>'.format(relative_src)
        elif src:
            self._script += '<script>{}</script>'.format(src)

    def end_body(self):
        """Ends the whole document. This should be called the last"""
        if self.write_copy_script:
            self.write(
                '<textarea id="c" class="invisible"></textarea>'
                '<script>'
                'function cp(t){'
                'var c=document.getElementById("c");'
                'c.value=t;'
                'c.select();'
                'try{document.execCommand("copy")}'
                'catch(e){}}'
                '</script>')

        self.write('</div>')
        self.write(self._script)
        self.write('</body></html>')

    # "Low" level writing
    def write(self, s):
        """Wrapper around handle.write"""
        self.handle.write(s)

    # With block
    def __enter__(self):
        # Sanity check
        parent = os.path.dirname(self.filename)
        if parent:
            os.makedirs(parent, exist_ok=True)

        self.handle = open(self.filename, 'w', encoding='utf-8')
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.handle.close()
