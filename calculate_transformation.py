"""
converts electrode (or for that matter, any point) coordinates in MRI space
to coordinates in freesurfer mesh space.
Requires subject ID to find coords data (in electrodenames_coordinates_native_and_T1.csv) and
the two matrices Norig and Torig which can be obtained using mri_info


Run:
    python voxcoords_to_fs.py <subject> <out_file>
to create a voxel_coordinates_fs.json file
"""

import logging
from mri_info import *
from numpy.linalg import inv
from config import paths
from localization import InvalidContactException
logger = logging.getLogger('submission')

def xdot(*args):
    """
    Reads electrodenames_coordinates_native_and_T1.csv, returning a dictionary of leads
    :param t1_file: path to electrodenames_coordinates_native_and_T1.csv file
    :returns: dictionary of form TODO {lead_name: {contact_name1: contact1, contact_name2:contact2, ...}}
    """
    return reduce(np.dot, args)


def read_and_tx(t1_file, fs_orig_t1,talxfmfile, localization,):
    """
    Reads electrodenames_coordinates_native_and_T1.csv, returning a dictionary of leads
    :param t1_file: path to electrodenames_coordinates_native_and_T1.csv file
    :returns: dictionary of form TODO {lead_name: {contact_name1: contact1, contact_name2:contact2, ...}}
    """

    # Get freesurfer matrices
    Torig = get_transform(fs_orig_t1, 'vox2ras-tkr')
    Norig = get_transform(fs_orig_t1, 'vox2ras')
    with open(talxfmfile) as txf:
        talxfm = np.matrix([x.strip().strip(';').split() for x in txf.readlines()[-3:]]).astype(float)
    logger.debug("Got transform")
    for line in open(t1_file):
        split_line = line.strip().split(',')

        # Contact name
        contact_name = split_line[0]

        # Contact location
        x = split_line[10]
        y = split_line[11]
        z = split_line[12]

        # Create homogeneous coordinate vector
        # coords = float(np.vectorize(np.matrix([x, y, z, 1.0])))
        coords = np.matrix([float(x), float(y), float(z), 1]).T
        
        # Compute the transformation
        fullmat = Torig * inv(Norig)
        fscoords = fullmat * coords
        fsaverage_coords = talxfm * coords
        logger.debug("Transforming {}".format(contact_name))

        fsx = fscoords[0]
        fsy = fscoords[1]
        fsz = fscoords[2]

        fsavgx = fsaverage_coords[0]
        fsavgy = fsaverage_coords[1]
        fsavgz = fsaverage_coords[2]

        # Enter into "leads" dictionary
        try:
            localization.set_contact_coordinate('fs', contact_name, [fsx, fsy, fsz], 'raw')
            localization.set_contact_coordinate('t1_mri', contact_name, [x, y, z])
            localization.set_contact_coordinate('fsaverage',contact_name,[fsavgx,fsavgy,fsavgz],'raw')
        except InvalidContactException:
            logger.warn('Invalid contact %s in file %s'%(contact_name,os.path.basename(t1_file)))
    logger.debug("Done with transform")
    return Torig,Norig,talxfm

def insert_transformed_coordinates(localization, files):
    Torig,Norig,talxfm = read_and_tx(files['coords_t1'], files['fs_orig_t1'],files['tal_xfm'], localization)
    localization.get_pair_coordinates('fs',pairs=localization.get_pairs(localization.get_lead_names()))
    localization.get_pair_coordinates('fsaverage',pairs=localization.get_pairs(localization.get_lead_names()))
    localization.get_pair_coordinates('t1_mri',pairs=localization.get_pairs(localization.get_lead_names()))
    return Torig,Norig,talxfm


def invert_transformed_coords(localization,Torig,Norig,talxfm):
    for contact in localization.get_contacts():
        fs_corrected = localization.get_contact_coordinate('fs',contact,coordinate_type='corrected')
        coords = np.matrix([float(x) for x in fs_corrected[0]]+[1]).T
        mri_coords = Norig * inv(Torig) * coords
        fsaverage_coords = talxfm * mri_coords
        mri_x = mri_coords[0]
        mri_y = mri_coords[1]
        mri_z = mri_coords[2]
        localization.set_contact_coordinate('t1_mri',contact,[mri_x,mri_y,mri_z],coordinate_type='corrected')
        localization.set_contact_coordinate('fsaverage',contact,[fsaverage_coords[i] for i in range(3)],coordinate_type='corrected')
    localization.get_pair_coordinates('fsaverage')


def file_locations_fs(subject):
    """
    Creates the default file locations dictionary
    :param subject: Subject name to look for files within
    :returns: Dictionary of {file_name: file_location}
    """
    files = dict(
        coord_t1=os.path.join(paths.rhino_root, 'data10', 'RAM', 'subjects', subject, 'imaging', subject, 'electrodenames_coordinates_native_and_T1.csv'),
        fs_orig_t1=os.path.join(paths.rhino_root, 'data', 'eeg', 'freesurfer', 'subjects', subject, 'mri', 'orig.mgz')
    )
    return files

if __name__ == '__main__':
    logger.setLevel(logging.DEBUG)
    import sys
    leads = build_leads_fs(file_locations(sys.argv[1]))
    leads_as_dict = leads_to_dict(leads)
    clean_dump(leads_as_dict, open(sys.argv[2],'w'), indent=2, sort_keys=True)

