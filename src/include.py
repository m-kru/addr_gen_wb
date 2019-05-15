""" That module contains handle_includes function
for recursive including XML files.
The function may be easily modified to handle
other types of files.
Written by Wojciech M. Zabolotny
wzab01<at>gmail.com
This is a free code (PUBLIC DOMAIN or CC0 1.0
Universal License). There is no warranty of any
kind. You use it on your own risk!
"""
import os.path
import re
R1 = r"<!--\s*include\s*(?P<fname>\S+)\s*-->"
P1 = re.compile(R1)
class LineLocation(object):
    """ Class LineLocation stores the origin of the
    block of source code lines.
    "start" is the location of the first line of the block
    "end" is the location of the last line of the block
    "fpath" is the path to the file from where the lines were
    read.
    """
    def __init__(self, start, end, fpath):
        self.start = start
        self.end = end
        self.fpath = fpath
    def adjust(self, shift):
        self.start += shift
        self.end += shift
    def tostr(self):
        return str(self.start)+","+str(self.end)+":"+self.fpath

def handle_includes(file_path, base_dir="./"):
    """ Function handle_includes replaces the include directives:
    <!-- include path/to/the/included_file -->
    with the contents of the included file.
    If the included file also contains include directives, they
    are handled recursively.
    The base_dir argument specifies base directory for relative
    paths.
    """
    # Check if the file_path is relative or absolute
    if file_path[0] == '/':
        # absolute
        full_file_path = file_path
    else:
        # relative
        full_file_path = base_dir + '/' + file_path
    # Read the file contents
    contents = open(full_file_path, 'r').read()
    # Create the base directory for possible further includes
    next_base_dir = os.path.dirname(full_file_path)
    # Find the include directives
    # Mark the start position
    start_pos = 0
    # Current number of lines
    start_line = 0
    # List of the parts of the string
    chunks = []
    lines = []
    incl_iter = P1.finditer(contents)
    for incl_instance in incl_iter:
        # Find the occurence of include
        include_span = incl_instance.span()
        # Put the unmodified part of the string to the list
        part = contents[start_pos:include_span[0]]
        chunks.append(part)
        # Find the number of the end line
        end_line = start_line + len(part.split('\n'))-1
        lines.append(LineLocation(start_line,end_line,file_path))
        start_line = end_line
        # Read the included file and handle nested includes
        replacement, rlines = handle_includes(incl_instance.groups()[0], next_base_dir)
        chunks.append(replacement)
        # Now adjust the line positions accorrding to the first line of the include
        for r in rlines:
            r.adjust(start_line)
        # Adjust the start line after the end of the include
        start_line = r.end
        # Append lines positions
        lines += rlines
        # Adjust the start position
        start_pos = include_span[1]
    # Add the final text (if any)
    part = contents[start_pos:]
    if len(part) > 0:
        chunks.append(part)
        # And add the final part line positions
        end_line = start_line + len(part.split('\n'))-1
        lines.append(LineLocation(start_line, end_line, file_path))
    # Now create and return the content with resolved includes
    res = ''.join(chunks)
    return res, lines
