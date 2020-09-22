import pyvisa
import time
#from pandas import DataFrame
import numpy
import sys
from lt_control import LT

_prefix = {'y': 1e-24,  # yocto
           'z': 1e-21,  # zepto
           'a': 1e-18,  # atto
           'f': 1e-15,  # femto
           'p': 1e-12,  # pico
           'n': 1e-9,   # nano
           'u': 1e-6,   # micro
           'm': 1e-3,   # mili
           'c': 1e-2,   # centi
           'd': 1e-1,   # deci
           'k': 1e3,    # kilo
           'M': 1e6,    # mega
           'G': 1e9,    # giga
           'T': 1e12,   # tera
           'P': 1e15,   # peta
           'E': 1e18,   # exa
           'Z': 1e21,   # zetta
           'Y': 1e24,   # yotta
    }

lt = LT('COM4')
if not lt.is_referenced():
    print('Stage not referenced! Reference now?(y/n) \nWarning: Stage will move until it hits the limit switch.')
    inp  = input()
    if not inp == 'y':
        sys.exit(0)
    else:
        lt.do_referencing()

lt.move_absolute(0)
# print('Continue?')
# input()

#lt.do_referencing()

# rm = pyvisa.ResourceManager()
# res = rm.list_resources('GPIB?*INSTR')
# gm_addr = res[0]
# gaussmeter = rm.open_resource(gm_addr)
# gaussmeter.query('AUTO 1')

#df = DataFrame(columns=['Steps','Field(T)','Distance(m)'])

# csv_sep = '\t'
# path = 'G:/Messungen/Magnet Kalibrierung/N42_25_5 Magnete/MagnetCalibration_test_slow.csv'

# with open(path, 'w') as f:
#     #f.write('SEP=' + csv_sep +'\n')
#     #df.to_csv(f, sep = csv_sep)
#     f.write('Steps\tDistance(mm)\tField(T)\n')
#     print('Steps\tDistance(mm)\tField(T)')
#     for i in numpy.arange(0, 35, .5):
#         lt.move_absolute_mm(i)
#         time.sleep(1)
#         mult = gaussmeter.query('FIELDM?').strip()
#         if len(mult) == 0:
#             mult = 1
#         else:
#             mult = _prefix[mult]
#         tesla = abs(float(gaussmeter.query('FIELD?'))*mult)
#         steps = lt.get_position()
#         #df.at[i,'Steps'] = steps
#         #df.at[i,'Field(T)'] = tesla
#         #df.at[i,'Distance(m)'] = steps*(1.25e-3/1600)
#         print('{0:d}\t{1:.3E} mm\t{2:.3E} T'.format(steps, lt.steps_to_mm(steps), tesla))
#         f.write('{0:d}\t{1:.3E}\t{2:.3E}\n'.format(steps, lt.steps_to_mm(steps), tesla))
    


#lt.move_absolute(0)
# gaussmeter.close()