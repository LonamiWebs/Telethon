def generate_errors(errors, f):
    # Exact/regex match to create {CODE: ErrorClassName}
    exact_match = []
    regex_match = []

    # Find out what subclasses to import and which to create
    import_base, create_base = set(), {}
    for error in errors:
        if error.subclass_exists:
            import_base.add(error.subclass)
        else:
            create_base[error.subclass] = error.int_code

        if error.has_captures:
            regex_match.append(error)
        else:
            exact_match.append(error)

    # Imports and new subclass creation
    f.write('from .rpcbaseerrors import RPCError, {}\n'
            .format(", ".join(sorted(import_base))))

    for cls, int_code in sorted(create_base.items(), key=lambda t: t[1]):
        f.write('\n\nclass {}(RPCError):\n    code = {}\n'
                .format(cls, int_code))

    # Error classes generation
    for error in errors:
        f.write('\n\nclass {}({}):\n    '.format(error.name, error.subclass))

        if error.has_captures:
            f.write('def __init__(self, request, capture=0):\n    '
                    '    self.request = request\n    ')
            f.write('    self.{} = int(capture)\n        '
                    .format(error.capture_name))
        else:
            f.write('def __init__(self, request):\n    '
                    '    self.request = request\n        ')

        f.write('super(Exception, self).__init__('
                '{}'.format(repr(error.description)))

        if error.has_captures:
            f.write('.format({0}=self.{0})'.format(error.capture_name))

        f.write(' + self._fmt_request(self.request))\n\n')
        f.write('    def __reduce__(self):\n        ')
        if error.has_captures:
            f.write('return type(self), (self.request, self.{})\n'.format(error.capture_name))
        else:
            f.write('return type(self), (self.request,)\n')

    # Create the actual {CODE: ErrorClassName} dict once classes are defined
    f.write('\n\nrpc_errors_dict = {\n')
    for error in exact_match:
        f.write('    {}: {},\n'.format(repr(error.pattern), error.name))
    f.write('}\n\nrpc_errors_re = (\n')
    for error in regex_match:
        f.write('    ({}, {}),\n'.format(repr(error.pattern), error.name))
    f.write(')\n')
