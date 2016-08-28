import parser.tl_generator

if __name__ == '__main__':
    if not parser.tl_generator.tlobjects_exist():
        print('First run. Generating TLObjects...')
        parser.tl_generator.generate_tlobjects('scheme.tl')
        print('Done.')

    pass
