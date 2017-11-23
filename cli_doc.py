from __future__ import print_function
import subprocess
import re

################

def run_cmd(cmd):
    cmd = "cli --quiet --no-login-prompt --user network-admin:test123 " + cmd
    try:
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        output = proc.communicate()[0]
        return output.strip().split('\n')
    except:
        print("Failed running cmd %s" % cmd)
        exit(0)

################
all_cmds_file = open("all_cmds", "w")

cmd_indicator = re.compile('^\w')
arg_indicator = re.compile('^\s[a-zA-Z\[]')

cmd_doc = {}

all_cmds = run_cmd("help")
for cmd in all_cmds:
    p_cmd = re.split(r'\s+', cmd)
    cmd_prefix = p_cmd[0]
    cmd_info = run_cmd("help %s" % cmd_prefix)
    skip = False
    for ilen in range(len(cmd_info)):
        info = cmd_info[ilen].rstrip()
        temp = re.split(r'\s+', info)
        cmd_arg, cmd_help = temp[0].strip(), " ".join(temp[1:])
        if cmd_indicator.match(info):
            if cmd_doc.get(cmd_arg, None):
                skip = True
                continue
            skip = False
            main_cmd = cmd_arg
            all_cmds_file.write(main_cmd+"\n")
            temp = info.split(" ")
            doc_len = len(temp[0]) - 7
            for i in info[len(temp[0]):]:
                if i != ' ':
                    break
                doc_len += 1
            cmd_doc[cmd_arg] = {'doc': cmd_help, 'args': []}
        elif arg_indicator.match(info) and not skip:
            arg = info[1:doc_len].strip()
            arg_doc = info[doc_len:].strip()
	    if arg == "[ switch switch-name ]" and not arg_doc:
		arg_doc = "switch name"
            elif not arg_doc:
                incr = 1
                arg_str = arg
                new_dl = doc_len - 9
                while (ilen + incr) < len(cmd_info):
                    future = cmd_info[ilen + incr].strip()
                    f_arg = future[:new_dl].strip()
                    f_arg_doc = future[new_dl:].strip()
                    arg_str += f_arg
                    if f_arg_doc:
                        arg = arg_str
                        arg_doc = f_arg_doc
                        break
                    incr += 1
            cmd_doc[main_cmd]['args'].append((arg, arg_doc))
        else:
            continue

################

with open('pn_ansible_lib.py', 'r') as FILE:
    PRE_DATA = FILE.read()

pn_cli_lib = open("pn_cli.py", "w")

def refine(txt):
    return txt.replace('-','_')

def struct_simple(option):
    return """        if '%s' in kwargs:
            command += \" %s %%s\" %% kwargs['%s']""" % (
               refine(option), option, refine(option))

def struct_single(option):
    return """        if '%s' in kwargs:
            command += \" %s\"""" % (refine(option), option)

def struct_array(option, choices):
    return """        if '%s' in kwargs:
            if kwargs['%s'] in %s:
                command += \" %s %%s\" %% kwargs['%s']
            else:
                print(\"Incorrect argument: %%s\") %% kwargs['%s']""" % (
                    refine(option), refine(option), choices, option,
                    refine(option), refine(option))

def struct_choice(choices):
    return """        if '%s' in kwargs:
            if kwargs['%s']:
                command += \" %s\"
            else:
                command += \" %s\"""" % (
                    refine(choices[0]), refine(choices[0]), choices[0],
                    choices[1])

def struct_range(option, start, end):
    return """        if '%s' in kwargs:
            if kwargs['%s'] in range(%d, %d):
                command += \" %s %%s\" %% kwargs['%s']
           """ % (refine(option), refine(option), int(start), int(end)+1,
                  option, refine(option))

simple = re.compile('^[a-zA-Z0-9-]+ [a-zA-Z0-9-]+$')
single = re.compile('^[a-zA-Z0-9-]+$')
complete_array = re.compile('^[a-zA-Z0-9-]+ ([^|]+\|)+[^|]+$')
choice = re.compile('^([a-zA-Z0-9-]+\|)+[a-zA-Z0-9-]+$')
rangetype = re.compile('^-?\d+\.+\d+G?$')
idtype = re.compile('^.*id$')
nidtype = re.compile('^[a-zA-Z0-9-]*id <[a-zA-Z0-9-]*id>$')
datetime = re.compile('^[a-zA-Z0-9-_]+ date/time: yyyy-mm-ddTHH:mm:ss')
duration = re.compile('^[a-zA-Z0-9-_]+ duration: #d#h#m#s')
hrtime = re.compile('^[a-zA-Z0-9-_]+ high resolution time: #ns')
mstime = re.compile('^.+\(ms\)$')
stime = re.compile('^.+\(s\)$')
name = re.compile('^.+name$')
filetype = re.compile('^.+file$')
vxlantype = re.compile('^.+vxlan$')
iptype = re.compile('^.+ ip$')
label = re.compile('^.+label$')
desc = re.compile('^.* .* description$')
nictype = re.compile('^.+ nic$')

show = re.compile('.+_show$')
status = re.compile('.+_status$')

pn_cli_lib.write(PRE_DATA)

for cmd in sorted(cmd_doc, key = lambda x: (x.split('-')[:-1],len(x))):
    refined_cmd = refine(cmd)
    pn_cli_lib.write("""
    def %s(self, **kwargs):
        command = '%s'\n""" % (refined_cmd, cmd))
    #if cmd not in CMD_FILTER:
    #    continue
    if "show" == cmd.split('-')[-1]:
	continue
    for cmd_arg in cmd_doc[cmd]['args']:
        raw = cmd_arg[0].strip("[]").strip()
        text = raw.split(" ")
        if show.match(refined_cmd) or status.match(refined_cmd):
            if text[0] == "formatting":
                break

        # Ignore unnecessary things
        if text[0:3] == "one or more".split(" "):
            continue
        elif text[0:3] == "at least 1".split(" "):
            continue
        elif text[0:3] == "any of the".split(" "):
            continue
        elif refine(text[0]) == refined_cmd:
            continue
        elif "selector" in raw:
            continue
        elif "following" in raw:
            continue
        elif "formatting" in raw:
            continue
        elif "pager" == cmd:
            continue
        elif "vrouter-vtysh-cmd" == cmd:
            continue

        # Handle the param 'if', which cant be passed as a kwarg
        if text[0] == 'if':
            text[0] = '_if'

        if simple.match(raw) or \
           datetime.match(raw) or \
           duration.match(raw) or \
           hrtime.match(raw) or \
           mstime.match(raw) or \
           stime.match(raw) or \
           name.match(raw) or \
           idtype.match(raw) or \
           nidtype.match(raw) or \
           nictype.match(raw) or \
           filetype.match(raw) or \
           vxlantype.match(raw) or \
           iptype.match(raw) or \
           label.match(raw) or \
           desc.match(raw):
            pn_cli_lib.write(struct_simple(text[0]) + '\n')

        elif single.match(raw):
            pn_cli_lib.write(struct_single(text[0]) + '\n')

        elif complete_array.match(raw):
            option = text[0]
            choices = text[1].split('|')
            pn_cli_lib.write(struct_array(option, choices) + '\n')

        elif choice.match(raw):
            options = raw.split('|')
            pn_cli_lib.write(struct_choice(options) + '\n')

        elif rangetype.match(text[1]):
            start = text[1].split('.')[0]
            end = text[1].split('.')[-1]
            if not end[-1].isdigit():
		end = end[:-1]
            pn_cli_lib.write(struct_range(text[0], start, end) + '\n')

        else:
            print("Unhandled cmd: %s >>%s<<" % (refined_cmd, raw))

    if show.match(refined_cmd):
        pn_cli_lib.write(" "*8 + "command = self.add_common_args(command, \
kwargs)\n")

    pn_cli_lib.write("""
        return self.send_command(command)
""")
