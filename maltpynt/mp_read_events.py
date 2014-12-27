from __future__ import division, print_function
from .mp_base import mp_root, mp_read_header_key, mp_ref_mjd
from .mp_io import mp_save_events
from .mp_io import MP_FILE_EXTENSION
import numpy as np


def mp_load_gtis(fits_file, gtistring=None):
    '''Loads GTI from HDU EVENTS of file fits_file'''
    from astropy.io import fits as pf
    import numpy as np

    if gtistring is None:
        gtistring = 'GTI'
    print("Loading GTIS from file" % fits_file)
    lchdulist = pf.open(fits_file, checksum=True)
    lchdulist.verify('warn')

    gtitable = lchdulist[gtistring].data
    gti_list = np.array([[a, b]
                         for a, b in zip(gtitable.field('START'),
                                         gtitable.field('STOP'))],
                        dtype=np.longdouble)
    lchdulist.close()
    return gti_list


def mp_load_events_and_gtis(fits_file, verbose=0, return_limits=False,
                            additional_columns=None, gtistring=None,
                            gti_file=None, hduname='EVENTS', column='TIME'):
    '''
    Loads event list from HDU EVENTS of file fits_file, with Good Time
    intervals. Optionally, returns additional columns of data from the same
    HDU of the events.
    Inputs:
        fits_file
        return_limits:  (bool) return the TSTART and TSTOP keyword values
        additional_columns: (optional) a list of keys corresponding to the
            additional columns to extract from the event HDU (ex.: ['PI', 'X'])
    Outputs:
        ev_list
        gtis
        additional_data: (dictionary of arrays) the key of the dictionary is
            the one specified in additional_colums. The data are an array with
            the values of the specified column in the fits file.
        t_start
        t_stop
    '''
    from astropy.io import fits as pf

    lchdulist = pf.open(fits_file)

    hdunames = [h.name for h in lchdulist]

    # Load data table
    try:
        lctable = lchdulist[hduname].data
    except:
        print('HDU %s not found. Trying first extension' % hduname)
        lctable = lchdulist[1].data

    # Read event list
    ev_list = np.array(lctable.field(column), dtype=np.longdouble)

    # Read TIMEZERO keyword and apply it to events
    try:
        timezero = np.longdouble(lchdulist[1].header['TIMEZERO'])
    except:
        print("TIMEZERO is 0")
        timezero = 0.

    if timezero != 0.:
        print("TIMEZERO != 0, correcting")
        ev_list += timezero

    # Read TSTART, TSTOP from header
    try:
        t_start = np.longdouble(lchdulist[1].header['TSTART'])
        t_stop = np.longdouble(lchdulist[1].header['TSTOP'])
    except:
        print("Tstart and Tstop error. using defaults")
        t_start = ev_list[0]
        t_stop = ev_list[-1]

    # Read and handle GTI extension
    if gtistring is None:
        accepted_gtistrings = ['GTI', 'STDGTI']
    else:
        accepted_gtistrings = [gtistring]

    if gti_file is None:
        # Select first GTI with accepted name
        try:
            gtiextn = [ix for ix, x in enumerate(hdunames)
                       if x in accepted_gtistrings][0]
            gtiext = lchdulist[gtiextn]
            gtitable = gtiext.data

            colnames = [col.name for col in gtitable.columns.columns]
            # Default: NuSTAR: START, STOP. Otherwise, try RXTE: Start, Stop
            if 'START' in colnames:
                startstr, stopstr = 'START', 'STOP'
            else:
                startstr, stopstr = 'Start', 'Stop'

            gtistart = np.array(gtitable.field(startstr), dtype=np.longdouble)
            gtistop = np.array(gtitable.field(stopstr), dtype=np.longdouble)
            gti_list = np.array([[a, b]
                                 for a, b in zip(gtistart,
                                                 gtistop)],
                                dtype=np.longdouble)

        except:
            print("%s Extension not found or invalid in %s!! Please check!!" %
                  (gtistring, fits_file))
            gti_list = np.array([[t_start, t_stop]],
                                dtype=np.longdouble)
    else:
        gti_list = mp_load_gtis(gti_file, gtistring)

    if additional_columns is not None:
        additional_data = {}
        for a in additional_columns:
            try:
                additional_data[a] = np.array(lctable.field(a))
            except:
                if a == 'PI':
                    print('Column PI not found. Trying with PHA')
                    additional_data[a] = np.array(lctable.field('PHA'))
                else:
                    raise Exception('Column' + a + 'not found')

    lchdulist.close()

    if return_limits:
        if additional_columns is not None:
            return ev_list, gti_list, additional_data, t_start, t_stop
        else:
            return ev_list, gti_list, t_start, t_stop
    else:
        if additional_columns is not None:
            return ev_list, gti_list, additional_data
        else:
            return ev_list, gti_list


def mp_treat_event_file(filename):

    print('Opening %s' % filename)

    instr = mp_read_header_key(filename, 'INSTRUME')
    additional_columns = ['PI']
    if instr == 'PCA':
        additional_columns.append('PCUID')

    mjdref = mp_ref_mjd(filename)
    events, gtis, additional, tstart, tstop = \
        mp_load_events_and_gtis(filename,
                                additional_columns=additional_columns,
                                return_limits=True)

    pis = additional['PI']
    out = {'time': events,
           'GTI': gtis,
           'PI': pis,
           'MJDref': mjdref,
           'Tstart': tstart,
           'Tstop': tstop,
           'Instr': instr
           }

    if instr == "PCA":
        out['PCU'] = np.array(additional['PCUID'], dtype=np.byte)

    outfile = mp_root(filename) + '_ev' + MP_FILE_EXTENSION
    mp_save_events(out, outfile)


if __name__ == "__main__":
    import argparse
    description = ('Read a cleaned event files and saves the relevant '
                   'information in a standard format')
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("files", help="List of files", nargs='+')
    args = parser.parse_args()
    files = args.files

    for f in files:
        mp_treat_event_file(f)
