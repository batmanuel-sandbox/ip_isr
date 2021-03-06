#
# LSST Data Management System
# Copyright 2008-2016 AURA/LSST.
#
# This product includes software developed by the
# LSST Project (http://www.lsst.org/).
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the LSST License Statement and
# the GNU General Public License along with this program.  If not,
# see <http://www.lsstcorp.org/LegalNotices/>.
#
import lsst.afw.cameraGeom as cameraGeom
import lsst.afw.cameraGeom.utils as cameraGeomUtils
import lsst.afw.image as afwImage
import lsst.pex.config as pexConfig
import lsst.pipe.base as pipeBase
from lsstDebug import getDebugFrame
from lsst.afw.display import getDisplay

__all__ = ["AssembleCcdTask"]


class AssembleCcdConfig(pexConfig.Config):
    doTrim = pexConfig.Field(
        doc="trim out non-data regions?",
        dtype=bool,
        default=True,
    )
    keysToRemove = pexConfig.ListField(
        doc="FITS headers to remove (in addition to DATASEC, BIASSEC, TRIMSEC and perhaps GAIN)",
        dtype=str,
        default=(),
    )

## @addtogroup LSST_task_documentation
## @{
## @page AssembleCcdTask
## @ref AssembleCcdTask_ "AssembleCcdTask"
## @copybrief AssembleCcdTask
## @}


class AssembleCcdTask(pipeBase.Task):
    """!
    @anchor AssembleCcdTask_

    @brief Assemble a set of amplifier images into a full detector size set of pixels.

    @section ip_isr_assemble_Contents Contents

     - @ref ip_isr_assemble_Purpose
     - @ref ip_isr_assemble_Initialize
     - @ref ip_isr_assemble_IO
     - @ref ip_isr_assemble_Config
     - @ref ip_isr_assemble_Debug
     - @ref ip_isr_assemble_Example

    @section ip_isr_assemble_Purpose Description

    This task assembles sections of an image into a larger mosaic.  The sub-sections
    are typically amplifier sections and are to be assembled into a detector size pixel grid.
    The assembly is driven by the entries in the raw amp information.  The task can be configured
    to return a detector image with non-data (e.g. overscan) pixels included.  The task can also
    renormalize the pixel values to a nominal gain of 1.  The task also removes exposure metadata that
    has context in raw amps, but not in trimmed detectors (e.g. 'BIASSEC').

    @section ip_isr_assemble_Initialize Task initialization

    @copydoc \_\_init\_\_

    @section ip_isr_assemble_IO Inputs/Outputs to the assembleCcd method

    @copydoc assembleCcd

    @section ip_isr_assemble_Config Configuration parameters

    See @ref AssembleCcdConfig

    @section ip_isr_assemble_Debug Debug variables

    The @link lsst.pipe.base.cmdLineTask.CmdLineTask command line task@endlink interface supports a
    flag @c -d to import @b debug.py from your @c PYTHONPATH; see <a
    href="http://lsst-web.ncsa.illinois.edu/~buildbot/doxygen/x_masterDoxyDoc/base_debug.html">
    Using lsstDebug to control debugging output</a> for more about @b debug.py files.

    The available variables in AssembleCcdTask are:
    <DL>
      <DT> @c display
      <DD> A dictionary containing debug point names as keys with frame number as value. Valid keys are:
        <DL>
          <DT> assembledExposure
          <DD> display assembled exposure
        </DL>
    </DL>

    @section ip_isr_assemble_Example A complete example of using AssembleCcdTask

    This code is in runAssembleTask.py in the examples directory, and can be run as @em e.g.
    @code
    python examples/runAssembleTask.py
    @endcode

    @dontinclude runAssembleTask.py
    Import the task.  There are other imports.  Read the source file for more info.
    @skipline AssembleCcdTask

    @dontinclude exampleUtils.py
    Create some input images with the help of some utilities in examples/exampleUtils.py
    @skip makeAssemblyInput
    @until inputData
    The above numbers can be changed.  The assumption that the readout corner is flipped on every other amp is
    hardcoded in createDetector.

    @dontinclude runAssembleTask.py
    Run the assembler task
    @skip runAssembler
    @until frame += 1

    <HR>
    To investigate the @ref ip_isr_assemble_Debug, put something like
    @code{.py}
    import lsstDebug
    def DebugInfo(name):
        di = lsstDebug.getInfo(name)        # N.b. lsstDebug.Info(name) would call us recursively
        if name == "lsst.ip.isr.assembleCcdTask":
            di.display = {'assembledExposure':2}
        return di

    lsstDebug.Info = DebugInfo
    @endcode
    into your debug.py file and run runAssembleTask.py with the @c --debug flag.


    Conversion notes:
        Display code should be updated once we settle on a standard way of controlling what is displayed.
    """
    ConfigClass = AssembleCcdConfig
    _DefaultName = "assembleCcd"

    def __init__(self, **kwargs):
        """!Initialize the AssembleCcdTask

        The keys for removal specified in the config are added to a default set:
        ('DATASEC', 'BIASSEC', 'TRIMSEC', 'GAIN')
        """
        pipeBase.Task.__init__(self, **kwargs)

        self.allKeysToRemove = ('DATASEC', 'BIASSEC', 'TRIMSEC', 'GAIN') + tuple(self.config.keysToRemove)

    def assembleCcd(self, assembleInput):
        """!Assemble a set of amps into a single CCD size image
        @param[in] assembleInput -- Either a dictionary of amp lsst.afw.image.Exposures or a single
                                    lsst.afw.image.Exposure containing all raw
                                    amps.  If a dictionary of amp exposures,
                                    the key should be the amp name.
        @return assembledCcd -- An lsst.afw.image.Exposure of the assembled amp sections.

        @throws TypeError with the following string:

        <DL>
          <DT> Expected either a dictionary of amp exposures or a single raw exposure
          <DD> The input exposures to be assembled do not adhere to the required format.
        </DL>

        @throws RuntimeError with the following string:

        <DL>
          <DT> No ccd detector found
          <DD> The detector set on the input exposure is not set.
        </DL>
        """
        ccd = None
        if isinstance(assembleInput, dict):
            # assembleInput is a dictionary of amp name: amp exposure

            # Assume all amps have the same detector, so get the detector from an arbitrary amp
            ccd = next(iter(assembleInput.values())).getDetector()

            def getNextExposure(amp):
                return assembleInput[amp.getName()]
        elif hasattr(assembleInput, "getMaskedImage"):
            # assembleInput is a single exposure
            ccd = assembleInput.getDetector()

            def getNextExposure(amp):
                return assembleInput
        else:
            raise TypeError("Expected either a dictionary of amp exposures or a single raw exposure")

        if ccd is None:
            raise RuntimeError("No ccd detector found")

        if not self.config.doTrim:
            outBox = cameraGeomUtils.calcRawCcdBBox(ccd)
        else:
            outBox = ccd.getBBox()
        outExposure = afwImage.ExposureF(outBox)
        outMI = outExposure.getMaskedImage()

        if self.config.doTrim:
            assemble = cameraGeom.assembleAmplifierImage
        else:
            assemble = cameraGeom.assembleAmplifierRawImage

        for amp in ccd:
            inMI = getNextExposure(amp).getMaskedImage()
            assemble(outMI, inMI, amp)
        #
        # If we are returning an "untrimmed" image (with overscans and extended register) we
        # need to update the ampInfo table in the Detector as we've moved the amp images into
        # place in a single Detector image
        #
        if not self.config.doTrim:
            ccd = cameraGeom.makeUpdatedDetector(ccd)

        outExposure.setDetector(ccd)
        self.postprocessExposure(outExposure=outExposure, inExposure=getNextExposure(ccd[0]))

        return outExposure

    def postprocessExposure(self, outExposure, inExposure):
        """Set exposure non-image attributes, including wcs and metadata and display exposure (if requested)

        Call after assembling the pixels

        @param[in,out]  outExposure assembled exposure:
                                    - removes unwanted keywords
                                    - sets calib, filter, and detector
        @param[in]      inExposure  input exposure
        """
        self.setWcs(outExposure=outExposure, inExposure=inExposure)

        exposureMetadata = inExposure.getMetadata()
        for key in self.allKeysToRemove:
            if exposureMetadata.exists(key):
                exposureMetadata.remove(key)
        outExposure.setMetadata(exposureMetadata)

        # note: Calib is not copied, presumably because it is assumed unknown in raw data
        outExposure.setFilter(inExposure.getFilter())
        outExposure.getInfo().setVisitInfo(inExposure.getInfo().getVisitInfo())

        frame = getDebugFrame(self._display, "assembledExposure")
        if frame:
            getDisplay(frame).mtv(outExposure)

    def setWcs(self, outExposure, inExposure):
        """Set output WCS = input WCS, adjusted as required for datasecs not starting at lower left corner

        @param[in,out]  outExposure     assembled exposure; wcs is set
        @param[in]      inExposure      input exposure
        """
        if inExposure.hasWcs():
            wcs = inExposure.getWcs()
            ccd = outExposure.getDetector()
            amp0 = ccd[0]
            if amp0 is None:
                raise RuntimeError("No amplifier detector information found")
            adjustedWcs = cameraGeomUtils.prepareWcsData(wcs, amp0, isTrimmed=self.config.doTrim)
            outExposure.setWcs(adjustedWcs)
