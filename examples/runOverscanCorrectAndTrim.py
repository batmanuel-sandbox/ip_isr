

if __name__ == "__main__":
    import eups
    import os
    import lsst.afw.image as afwImage
    import lsst.daf.base as dafBase
    import lsst.pex.logging as pexLog
    import lsst.pex.policy as pexPolicy
    import lsst.ip.isr.OverscanCorrectAndTrim as ipIsrOver 

    pexLog.Trace.setVerbosity("lsst.ip.isr", 4)
    
    dataDir = eups.productDir("afwdata")
    if not dataDir:
        raise RuntimeError("Must set up afwdata to run this program.")
    isrDir = eups.productDir("ip_isr")
    if not isrDir:
        raise RuntimeError("Must set up ip_isr to run this program.")
    
    chunkExposureInPath = os.path.join(dataDir, "satStageTestExposure_1")
    isrPolicyPath = os.path.join(isrDir, "pipeline", "isrPolicy.paf")
    chunkExposureOutPath = os.path.join(dataDir, "overStageTestExposure_1")
    
    memId0 = dafBase.Citizen_getNextMemId()

    chunkExposure = afwImage.ExposureD()
    chunkExposure.readFits(chunkExposureInPath)

    isrPolicy = pexPolicy.Policy.createPolicy(isrPolicyPath)
    
    ipIsrOver.overscanCorrectAndTrim(chunkExposure, isrPolicy)

    pexLog.Trace("lsst.ip.isr.overscanCorrectAndTrim", 4, "Writing chunkExposure to %s [_img|var|msk.fits]" % (chunkExposureOutPath,))
    chunkExposure.writeFits(chunkExposureOutPath)
    
    # check for memory leaks
    if dafBase.Citizen_census(0, memId0) != 0:
        print dafBase.Citizen_census(0, memId0), "Objects leaked:"
        print dafBase.Citizen_census(dafBase.cout, memId0)
