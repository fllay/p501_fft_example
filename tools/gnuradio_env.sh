# Source this to use GNU Radio 3.10 / UHD 4.8 (radioconda in ~/radioconda) with the B210:
#   source tools/gnuradio_env.sh
#   gnuradio-companion          # flowgraphs
#   uhd_find_devices            # the B210 (USB 3)
# UHD_IMAGES_DIR points to the firmware/FPGA images already installed with the system UHD 4.6
# (/usr/local/share/uhd/images); radioconda ships none. Nothing in that folder is modified.
export PATH=/home/pi/radioconda/bin:$PATH
export UHD_IMAGES_DIR=/usr/local/share/uhd/images
