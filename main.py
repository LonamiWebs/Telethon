from parser.tl_parser import TLParser


if __name__ == '__main__':

    parser = TLParser()
    for tlobject in parser.parse_file('parser/scheme.tl'):
        print(tlobject)
