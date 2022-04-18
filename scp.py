# Based on https://pydicom.github.io/pynetdicom/stable/examples/storage.html#storage-scp
import os
import string

from pydicom import dcmread

# from pydicom.uid import JPEG2000Lossless, JPEGBaseline, JPEGLosslessSV1
from pydicom.uid import JPEG2000Lossless, JPEGBaseline, JPEGLossless
from pynetdicom import AE, StoragePresentationContexts, build_context, debug_logger, evt
from pynetdicom.sop_class import (
    UltrasoundImageStorage,
    UltrasoundMultiframeImageStorage,
    VerificationSOPClass,
)


# Implement a handler evt.EVT_C_STORE
def handle_store(event):
    """Handle a C-STORE request event. Write data to file system. Send data to Orthanc"""

    # --------------------------------------------------------------------------
    # Get the data
    #

    # Decode the C-STORE request's *Data Set* parameter to a pydicom Dataset
    dataset = event.dataset

    # Add the File Meta Information
    dataset.file_meta = event.file_meta

    # Get values from dataset
    instance_num = str(dataset["InstanceNumber"].value)
    patient_name = str(dataset["PatientName"].value)
    patient_id = str(dataset["PatientID"].value)
    study_date = str(dataset["StudyDate"].value)
    study_time = str(dataset["StudyTime"].value)
    series_desc = ""
    if "SeriesDescription" in dataset:
        series_desc = str(dataset["SeriesDescription"].value)
    series_num = str(dataset["SeriesNumber"].value)
    modality = str(dataset["Modality"].value)
    coilstring = None  # Save individual coil images if they exist
    try:
        coilstring = str(dataset[0x051100F].value)
        # Clean up
        for char in string.punctuation:
            coilstring = coilstring.replace(char, "")
        print("SCP: CoilString found: %s" % coilstring)
    except KeyError:
        print("SCP: CoilString not found")

    # Clean up
    patient_name = patient_name.replace("^", "")
    dataset["PatientName"].value = patient_name

    # --------------------------------------------------------------------------
    # Write it the file system
    #

    # Use modality, patient, study, imaging series and sometimes coilstring values to define directory tree and filename
    # unless value is empty string, in which case filter. E.g. create dir '4' instead of '4_' when
    # series_desc == ''.
    subdir_0 = modality
    subdir_1 = "_".join(filter(None, [patient_name, patient_id]))
    subdir_2 = "_".join(filter(None, [patient_name, study_date, study_time]))
    subdir_3 = "_".join(filter(None, [series_num, series_desc]))
    filename = "_".join(filter(None, [patient_name, series_num, instance_num]))
    if coilstring:
        filename = "_".join(
            filter(None, [patient_name, series_num, instance_num, coilstring])
        )
    filename += ".dcm"

    # Make directories
    try:
        os.mkdir(os.path.join(DATADIR, subdir_0))
    except FileExistsError:
        pass
    try:
        os.mkdir(os.path.join(DATADIR, subdir_0, subdir_1))
    except FileExistsError:
        pass
    try:
        os.mkdir(os.path.join(DATADIR, subdir_0, subdir_1, subdir_2))
    except FileExistsError:
        pass
    try:
        os.mkdir(os.path.join(DATADIR, subdir_0, subdir_1, subdir_2, subdir_3))
    except FileExistsError:
        pass

    # Configure perms
    if not DEBUG:
        os.chown(subdir_0, 101, gid=100)
        os.chown(os.path.join(DATADIR, subdir_0, subdir_1), 101, gid=100)
        os.chown(os.path.join(DATADIR, subdir_0, subdir_1, subdir_2), 101, gid=100)
        os.chown(
            os.path.join(DATADIR, subdir_0, subdir_1, subdir_2, subdir_3), 101, gid=100
        )

    # Save the dataset using modality, patient, study, imaging series as directory tree and filename
    path = os.path.join(subdir_0, subdir_1, subdir_2, subdir_3)
    fq_path = os.path.join(DATADIR, path, filename)
    dataset.save_as(fq_path, write_like_original=False)

    # Configure perms
    if not DEBUG:
        os.chown(path, 101, gid=100)

    # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
    #
    # Send it to Orthanc
    #
    # Based on https://pydicom.github.io/pynetdicom/stable/examples/storage.html#storage-scu

    # Read in our DICOM dataset
    # ds = dcmread(path)

    # Associate with peer AE running Orthanc at ORTHANC_IP_ADDRESS and port 4242
    try:
        assoc = ae.associate(ORTHANC_IP_ADDRESS, 4242)
        if assoc.is_established:
            # Use the C-STORE service to send the dataset
            assoc.send_c_store(dataset)
            # Release the association
            assoc.release()
    except ValueError:
        # https://github.com/pydicom/pynetdicom/issues/599
        assoc = ae.associate(
            ORTHANC_IP_ADDRESS,
            4242,
            contexts=[
                # UltrasoundMultiframeImageStorage + jpegs
                build_context(
                    UltrasoundMultiframeImageStorage,
                    JPEG2000Lossless,
                ),
                build_context(
                    UltrasoundMultiframeImageStorage,
                    JPEGBaseline,
                ),
                build_context(
                    UltrasoundMultiframeImageStorage,
                    JPEGLossless,
                ),
                # UltrasoundImageStorage + jpegs
                build_context(
                    UltrasoundImageStorage,
                    JPEG2000Lossless,
                ),
                build_context(
                    UltrasoundImageStorage,
                    JPEGBaseline,
                ),
                build_context(
                    UltrasoundImageStorage,
                    JPEGLossless,
                ),
            ],
        )
        if assoc.is_established:
            # Use the C-STORE service to send the dataset
            assoc.send_c_store(dataset)
            # Release the association
            assoc.release()

    # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>

    # Return a 'Success' status
    return 0x0000


handlers = [(evt.EVT_C_STORE, handle_store)]

# ------------------------------------------------------------------------------

# Initialise the Application Entity
ae = AE()

# Add the supported presentation contexts
# https://github.com/pydicom/pynetdicom/issues/591#issuecomment-798992575
# https://github.com/pydicom/pynetdicom/issues/591#issuecomment-801492853
for cx in StoragePresentationContexts:
    cx.add_transfer_syntax(JPEGBaseline)
    #    cx.add_transfer_syntax(JPEGLosslessSV1)
    cx.add_transfer_syntax(JPEGLossless)
    cx.add_transfer_syntax(JPEG2000Lossless)
ae.supported_contexts = StoragePresentationContexts

# Ultrasound wants to verify
# https://pydicom.github.io/pynetdicom/stable/examples/verification.html#verification-scp
ae.add_supported_context(VerificationSOPClass)

# Set requested presentation context for storage-scu to send to Orthanc
ae.requested_contexts = StoragePresentationContexts

# --------------------------------------------------------------------------------

# Get Orthanc IP address or bust
ORTHANC_IP_ADDRESS = os.environ.get("ORTHANC_IP_ADDRESS", None)
if not ORTHANC_IP_ADDRESS:
    print("Please `export ORTHANC_IP_ADDRESS=<ip_address>` before running scp.py")
    exit(1)

# Get data path or bust
DATADIR = os.environ.get("DATADIR", None)
if not DATADIR:
    print("Please `export DATADIR=/path/to/files` before running scp.py")
    exit(1)

# Debug if DEBUG
DEBUG = os.environ.get("DEBUG", None)
if DEBUG:
    debug_logger()

# --------------------------------------------------------------------------------

# Start listening for incoming association requests
ae.start_server(("", 104), evt_handlers=handlers)
