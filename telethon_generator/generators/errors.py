def generate_errors(errors, f):
    f.write('_captures = {\n')
    for error in errors:
        if error.capture_name:
            f.write(f"    {error.canonical_name!r}: {error.capture_name!r},\n")
    f.write('}\n')

    f.write('\n\n_descriptions = {\n')
    for error in errors:
        if error.description:
            f.write(f"    {error.canonical_name!r}: {error.description!r},\n")
    f.write('}\n')
