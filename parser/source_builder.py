from io import StringIO


class SourceBuilder:
    """This class should be used to build .py source files"""

    def __init__(self, out_stream=None, indent_size=4):
        self.current_indent = 0
        self.on_new_line = False
        self.indent_size = indent_size

        if out_stream is None:
            self.out_stream = StringIO()
        else:
            self.out_stream = out_stream

    def indent(self):
        self.write(' ' * (self.current_indent * self.indent_size))

    def write(self, string):
        if self.on_new_line:
            self.on_new_line = False  # We're not on a new line anymore
            if string.strip():  # If the string was not empty, indent; Else it probably was a new line
                self.indent()

        self.out_stream.write(string)

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
        self.out_stream.seek(0)
        return self.out_stream.read()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.out_stream.flush()
        self.out_stream.close()
