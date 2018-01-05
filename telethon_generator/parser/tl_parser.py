import re

from .tl_object import TLObject


class TLParser:
    """Class used to parse .tl files"""

    @staticmethod
    def parse_file(file_path, ignore_core=False):
        """This method yields TLObjects from a given .tl file"""

        with open(file_path, encoding='utf-8') as file:
            # Start by assuming that the next found line won't
            # be a function (and will hence be a type)
            is_function = False

            # Read all the lines from the .tl file
            for line in file:
                # Strip comments from the line
                comment_index = line.find('//')
                if comment_index != -1:
                    line = line[:comment_index]

                line = line.strip()
                if line:
                    # Check whether the line is a type change
                    # (types <-> functions) or not
                    match = re.match('---(\w+)---', line)
                    if match:
                        following_types = match.group(1)
                        is_function = following_types == 'functions'

                    else:
                        try:
                            result = TLObject.from_tl(line, is_function)
                            if not ignore_core or not result.is_core_type():
                                yield result
                        except ValueError as e:
                            if 'vector#1cb5c415' not in str(e):
                                raise

    @staticmethod
    def find_layer(file_path):
        """Finds the layer used on the specified scheme.tl file"""
        layer_regex = re.compile(r'^//\s*LAYER\s*(\d+)$')
        with open(file_path, encoding='utf-8') as file:
            for line in file:
                match = layer_regex.match(line)
                if match:
                    return int(match.group(1))
