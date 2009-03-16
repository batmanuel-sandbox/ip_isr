from lsst.pex.harness.Stage import Stage
from lsst.daf.base import DateTime, PropertySet

import lsst.ip.isr.calibDatabase as calibDatabase

class IdentifyCalibrationProductsStage(Stage):
    def __init__(self, stageId=-1, stagePolicy=None):
        Stage.__init__(self, stageId, stagePolicy)
        self.cdb = calibDatabase.CalibDB(self._policy.get("calibDbPath"))

    def process(self):
        self.activeClipboard = self.inputQueue.getNextDataset()

        eventName = self._policy.get("eventName")
        event = self.activeClipboard.get(eventName)
        when = DateTime(event.get("dateObs"))
        
        expTime = event.get("expTime")
        darkPolicy = self._policy.get("darkPolicy")
        darkCalibList = self.cdb.lookup(when, "dark", event.get("ccdId"),
                event.get("ampId"), all=True)
        darkTimeList = []
        for d in darkCalibList:
            darkTimeList.append(d.expTime)
        darkTimeList.sort()
        if darkPolicy == "min":
            darkExpTime = darkTimeList[0]
        elif darkPolicy == "max":
            darkExpTime = darkTimeList[-1]
        elif darkPolicy == "closest":
            minDist = abs(expTime - darkTimeList[0])
            minExpTime = darkTimeList[0]
            for i in xrange(1, len(darkTimeList)):
                dist = abs(expTime - darkTimeList[i])
                if dist < minDist:
                    minDist = dist
                    minExpTime = darkTimeList[i]
            darkExpTime = minExpTime
        else:
            raise RuntimeError, "Unrecognized darkPolicy: " + str(darkPolicy)


        biasPath = self.cdb.lookup(when, "bias", event.get("ccdId"),
                event.get("ampId"))
        darkPath = self.cdb.lookup(when, "dark", event.get("ccdId"),
                event.get("ampId"), expTime=darkExpTime)
        defectPath = self.cdb.lookup(when, "defect", event.get("ccdId"),
                event.get("ampId"))
        flatPath = self.cdb.lookup(when, "flat", event.get("ccdId"),
                event.get("ampId"), filter=event.get("filter"))
#         fringePath = self.cdb.lookup(when, "fringe", event.get("ccdId"),
#                 event.get("ampId"), filter=event.get("filter"))
        linearizePath = self.cdb.lookup(when, "linearize", event.get("ccdId"),
                event.get("ampId"))

        calibData = PropertySet()
        calibData.set("biasPath", biasPath)
        calibData.set("darkPath", darkPath)
        calibData.set("defectPath", defectPath)
        calibData.set("flatPath", flatPath)
#         calibData.set("fringePath", fringePath)
        calibData.set("linearizePath", linearizePath)
        self.activeClipboard.put("calibData", calibData)

        self.outputQueue.addDataset(self.activeClipboard)
