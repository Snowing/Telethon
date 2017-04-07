import os
import re
import sys
from docs.docs_writer import DocsWriter

# Small trick so importing telethon_generator works
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from telethon_generator.parser import TLParser, TLObject


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

        with DocsWriter(filename, type_to_path_function=get_path_for_type) as docs:
            docs.write_head(
                title=get_class_name(tlobject),
                relative_css_path=paths['css'])

            # Create the menu (path to the current TLObject)
            docs.set_menu_separator(paths['arrow'])
            docs.add_menu('API',
                          link=paths['index_all'])

            docs.add_menu('Methods' if tlobject.is_function else 'Constructors',
                          link=paths['index_methods'] if tlobject.is_function else paths['index_constructors'])

            if tlobject.namespace:
                docs.add_menu(tlobject.namespace,
                              link='index.html')

            docs.add_menu(get_file_name(tlobject))
            docs.end_menu()

            # Create the page title
            docs.write_title(get_class_name(tlobject))

            # Write the code definition for this TLObject
            docs.write_code(tlobject)

            docs.write_title('Parameters' if tlobject.is_function else 'Members', level=3)

            # Sort the arguments in the same way they're sorted on the generated code (flags go last)
            args = sorted([a for a in tlobject.args if
                           not a.flag_indicator and not a.generic_definition],
                          key=lambda a: a.is_flag)
            if args:
                # Writing parameters
                docs.begin_table(column_count=3)

                for arg in args:
                    # Name row
                    docs.add_row(arg.name,
                                 bold=True)

                    # Type row
                    docs.add_row(arg.type,
                                 link=get_path_for_type(arg.type, relative_to=filename),
                                 align='center')

                    # Create a description for this argument
                    description = ''
                    if arg.is_vector:
                        description += 'A list must be supplied for this argument. '
                    if arg.is_generic:
                        description += 'A different MTProtoRequest must be supplied for this argument. '
                    if arg.is_flag:
                        description += 'This argument can be omitted. '

                    docs.add_row(description.strip())

                docs.end_table()
            else:
                if tlobject.is_function:
                    docs.write_text('This request takes no input parameters.')
                else:
                    docs.write_text('This type has no members.')

            docs.end_body()

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

        with DocsWriter(filename, type_to_path_function=get_path_for_type) as docs:
            docs.write_head(
                title=get_class_name(name),
                relative_css_path=paths['css'])

            docs.set_menu_separator(paths['arrow'])
            docs.add_menu('API',
                          link=paths['index_all'])

            docs.add_menu('Types',
                          link=paths['index_types'])

            if namespace:
                docs.add_menu(namespace,
                              link='index.html')

            docs.add_menu(get_file_name(name))
            docs.end_menu()

            # Main file title
            docs.write_title(get_class_name(name))

            docs.write_title('Available constructors', level=3)
            if not constructors:
                docs.write_text('This type has no constructors available.')
            elif len(constructors) == 1:
                docs.write_text('This type has one constructor available.')
            else:
                docs.write_text('This type has %d constructors available.' % len(constructors))

            docs.begin_table(1)
            for constructor in constructors:
                # Constructor full name
                link = get_create_path_for(constructor)
                link = get_relative_path(link, relative_to=filename)
                docs.add_row(get_class_name(constructor),
                             link=link,
                             align='center')
            docs.end_table()

            docs.write_title('Methods returning this type', level=3)
            functions = tlfunctions.get(tltype, [])
            if not functions:
                docs.write_text('No method returns this type.')
            elif len(functions) == 1:
                docs.write_text('Only the following method returns this type.')
            else:
                docs.write_text('The following %d methods return this type as a result.' % len(functions))

            docs.begin_table(1)
            for function in functions:
                link = get_create_path_for(function)
                link = get_relative_path(link, relative_to=filename)
                docs.add_row(get_class_name(function),
                             link=link,
                             align='center')
            docs.end_table()
            docs.end_body()

    # Done, written all functions, constructors and types


if __name__ == '__main__':
    print('Generating documentation...')
    generate_documentation('../telethon_generator/scheme.tl')
    print('Done.')
