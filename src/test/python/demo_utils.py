# utility to select object by id
def select_id(identifier, objects):
    for o in objects:
        if o.id == identifier:
            return o
    return None

# utility to print id and name of objects
def print_objs(objects):
    print '=========='
    for o in objects:
        print '%s -- %s' % (o.id, o.name)
    print '=========='
