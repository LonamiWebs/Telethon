
class SourceBuilder:
    """This class should be used to build .py source files"""

    def __init__(self, indent_size=4):
        self.current_indent = 0
        self.on_new_line = False
        self.indent_size = indent_size

        self.buffer = []

    def indent(self):
        self.write(' ' * (self.current_indent * self.indent_size))

    def write(self, string):
        if self.on_new_line:
            self.on_new_line = False  # We're not on a new line anymore
            self.indent()

        self.buffer += list(string)

    def writeln(self, string=''):
        self.write(string + '\n')
        self.on_new_line = True

        # If we're writing a block, increment indent for the next time
        if string and string[-1] == ':':
            self.current_indent += 1

    def end_block(self):
        self.current_indent -= 1
        self.writeln()

    def __str__(self):
        if self.buffer:
            return ''.join(self.buffer)
        else:
            return ''
