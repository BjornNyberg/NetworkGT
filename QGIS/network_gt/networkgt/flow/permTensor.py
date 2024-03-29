'''This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.'''

import os, math
from qgis.PyQt.QtCore import QCoreApplication, QVariant

from qgis.core import *
from qgis.PyQt.QtGui import QIcon

class permTensor(QgsProcessingAlgorithm):

    Network = "Branches"
    TP = 'Topology Parameters'
    mp = 'Matrix Permability'
    Rotation = 'Rotation'
    mpField = 'Matrix Field'
    ftField = 'Transmisivity Field'
    hC = 'HC'
    Output = 'Output'

    def __init__(self):
        super().__init__()

    def name(self):
        return "Permeability Tensor"

    def tr(self, text):
        return QCoreApplication.translate("Permeability Tensor", text)

    def displayName(self):
        return self.tr("Permeability Tensor")

    def group(self):
        return self.tr("5. Flow")

    def shortHelpString(self):
        return self.tr("Calculates an analytical estimate of effective permeability (fracture network plus matrix) for a specified sample area/contour grid. The user has the option to correct the effective permeability using a topology based hydraulic connectivity measure for the fracture network. \n Inputs are a branch network linestring and its associated topology parameters polygon/contour grid. The output adds fields to the attribute table of the topology parameters polygon/contour grid defining an effective permeability tensor (Kxx, Kxy, Kyy) and values for the principle permeability axis (K1, K2, K1 azimuth). Permeablity is given in millidarcy's (mD). \n N.B. The branch linestring must have associated fracture transmissivity values.\n Please refer to the help button for more information.")

    def groupId(self):
        return "5. Flow"

    def helpUrl(self):
        return "https://github.com/BjornNyberg/NetworkGT/wiki/5.-Flow-Assessment-Assessment"

    def createInstance(self):
        return type(self)()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.Network,
            self.tr("Branches"),
            [QgsProcessing.TypeVectorLine]))

        self.addParameter(QgsProcessingParameterFeatureSource(
            self.TP,
            self.tr("Topology Parameters"),
            [QgsProcessing.TypeVectorPolygon]))

        self.addParameter(QgsProcessingParameterNumber(
            self.Rotation,
            self.tr("Rotation"),
            QgsProcessingParameterNumber.Double,
            0.0,
            minValue=0.0,
            maxValue=90.0))

        self.addParameter(QgsProcessingParameterNumber(
            self.mp,
            self.tr("Matrix Permeability"),
            QgsProcessingParameterNumber.Double,
            0.0001,
            minValue=0.000001))

        self.addParameter(QgsProcessingParameterField(self.mpField,
                                self.tr('Matrix Permeability Field'), parentLayerParameterName=self.TP, type=QgsProcessingParameterField.Numeric,optional=True))
        self.addParameter(QgsProcessingParameterField(self.ftField,
                                self.tr('Transmisivity Field'), parentLayerParameterName=self.Network, type=QgsProcessingParameterField.Numeric,optional=True))
        self.addParameter(QgsProcessingParameterBoolean(self.hC,
                    self.tr("Hydraulic Connectivity"),True))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.Output, self.tr("Permeability Tensor"), QgsProcessing.TypeVectorPolygon, '',optional=True))

    def processAlgorithm(self, parameters, context, feedback):

        try:
            import numpy as np
        except Exception as e:
            feedback.reportError(QCoreApplication.translate('Error','%s'%(e)))
            feedback.reportError(QCoreApplication.translate('Error',' '))
            feedback.reportError(QCoreApplication.translate('Error','Error loading modules - please install the necessary dependencies'))
            return {}

        Network = self.parameterAsLayer(parameters, self.Network, context)
        TP = self.parameterAsLayer(parameters, self.TP, context)
        mpF = self.parameterAsString(parameters, self.mpField, context)
        tF = self.parameterAsString(parameters, self.ftField, context)
        rotation = parameters[self.Rotation]
        mP = parameters[self.mp]
        hcB = parameters[self.hC]

        P = 15

        new_fields = ['Kxx','Kxy','Kyy','K1 Azimuth','K1','K2','K1_K2']


        if self.Output in parameters:
            fields = QgsFields()
            for field in TP.fields():
                if field.name() not in new_fields:
                    fields.append(QgsField(field.name(), field.type()))

            for field in new_fields:
                fields.append(QgsField(field, QVariant.Double))

            (writer, dest_id) = self.parameterAsSink(parameters, self.Output, context,
                                                     fields, QgsWkbTypes.Polygon, TP.sourceCrs())
        else:

            pr = TP.dataProvider()

            for field in new_fields:
                if TP.fields().indexFromName(field) == -1:
                    pr.addAttributes([QgsField(field, QVariant.Double)])

            TP.updateFields()
            idxs = []
            for field in new_fields:
                idxs.append(TP.fields().indexFromName(field))

        Ti1, Ti2, Ti4 = {}, {},{}
        feedback.pushInfo(QCoreApplication.translate('Output','Calculating Tangential Vector Tensor'))

        features = Network.selectedFeatures()
        total = Network.selectedFeatureCount()
        if len(features) == 0:
            features = Network.getFeatures()
            total = Network.featureCount()
        total = 100.0/total

        for enum,feature in enumerate(features):
            if total != -1:
                feedback.setProgress(int(enum*total))
            geom = feature.geometry()
            if QgsWkbTypes.isSingleType(geom.wkbType()):
                geomF = [geom.asPolyline()]
            else:
                geomF = geom.asMultiPolyline()

            if len(geomF) == 0:
                feedback.reportError(QCoreApplication.translate('Error','Warning - skipping null geometry linestring.'))
                continue

            x,y = 0,0
            for part in geomF:
                startx = None
                for point in part:
                    if startx == None:
                        startx,starty = point
                        continue
                    endx,endy=point

                    dx = endx - startx
                    dy =  endy - starty

                    l = math.sqrt((dx**2)+(dy**2))
                    angle = math.degrees(math.atan2(dy,dx))
                    x += math.cos(math.radians(angle)) * l
                    y += math.sin(math.radians(angle)) * l

                    startx,starty = endx,endy

            a = 90 - np.around(math.degrees(math.atan2(y, x)), decimals=4)
            if a > 180:
                a -= 180
            elif a < 0:
                a += 180

           # a = np.around(math.degrees(math.atan2(y, x)), decimals=4)
           # a = a%360
           # if a > 180:
           #     a -= 180

            bLen = geom.length()
            if tF:
                t =  feature[tF]
                if type(t) != float:
                    feedback.reportError(QCoreApplication.translate('Error','Error - Transmisivity field contains non float values'))
                    return {}

            else:
                t = feature['Transmisiv']
                if type(t) != float:
                    feedback.reportError(QCoreApplication.translate('Error','Error - Transmisivity field contains non float values'))
                    return {}

            FID = feature['Sample_No_']
            if FID not in Ti1:
                Ti1[FID] = 0
                Ti2[FID] = 0
                Ti4[FID] = 0

            i1 =(bLen*t)*((1-((math.sin(math.radians(90-a)))**2)))
            i2 =(bLen*t)*((math.cos(math.radians(90-a)))*(math.sin(math.radians(90-a))))
            i4 =(bLen*t)*((1-((math.cos(math.radians(90-a)))**2)))

            Ti1[FID] += i1
            Ti2[FID] += i2
            Ti4[FID] += i4

        feedback.pushInfo(QCoreApplication.translate('Output','Calculating Permability Tensor'))

        traces,maxV = [],[]

        features = TP.selectedFeatures()
        total = TP.selectedFeatureCount()
        if len(features) == 0:
            features = TP.getFeatures()
            total = TP.featureCount()
        total = 100.0/total

        if self.Output in parameters:
            fet = QgsFeature()
        else:
            TP.startEditing()

        for enum,feature in enumerate(features):
            if total != -1:
                feedback.setProgress(int(enum*total))
            try:
                FID = feature['Sample_No_']
                Area = feature['Area']

                if mpF:
                    mPv = feature[mpF]
                    if type(mPv) != float:
                        feedback.reportError(QCoreApplication.translate('Error','Error - Matrix permeability field contains non float values'))
                        return {}
                else:
                    mPv = mP

                if FID in Ti1:
                    I = feature['I']
                    Y = feature['Y']
                    X = feature['X']

                    if hcB:
                        v1 = 4*X+2*Y
                        v2 = 4*X+2*Y+I

                        if v1 == 0:
                            hC = 0
                            if v2 == 0:
                                hC = 0.81
                        else:
                            hC = ((v1/v2)*2.94)-2.13
                            if hC < 0:
                                hC = 0
                        mPv = (1-hC)*mPv
                    else:
                        hC = 1

                    Ti1v = Ti1[FID]
                    Ti2v = Ti2[FID]
                    Ti4v = Ti4[FID]

                    Kxx =((hC/Area)*Ti1v)+mPv
                    Kxy =(hC/Area)*Ti2v
                    Kyy =((hC/Area)*Ti4v)+mPv

                else:
                    Kxx = mPv
                    Kxy = 0.0
                    Kyy = mPv

                p = Kyy*Kyy+Kxy*Kxy+Kxy*Kxy+Kxx*Kxx
                q = Kyy*Kxx-Kxy*Kxy

                K1 = math.sqrt((p+math.sqrt(p*p-4*q*q))/2)
                K2 = math.sqrt((p-math.sqrt(p*p-4*q*q))/2)
                if K2 == 0:
                    K12 = 0
                else:
                    K12 = K1/K2

                if K12 == 1:
                    K1a = 0
                else:
                    try:
                        x,y = 2*(Kxy*Kxx+Kyy*Kxy),(Kyy*Kyy)+(Kxy*Kxy)-(Kxy*Kxy)-(Kxx*Kxx)
                        K1a = math.atan2(x,y)/2/(math.pi/180)
                    except Exception:
                        K1a = -1
                if self.Output in parameters:
                    rows = []
                    for field in TP.fields():
                        if field.name() not in new_fields:
                            rows.append(feature[field.name()])
                    rows.extend([round(Kxx, P), round(Kxy, P),round(Kyy, P),round(K1a, P), round(K1, P),round(K2, P),round(K12, P)])
                    if rotation > 0:
                        rows.append(round((Kyy*(math.cos(rotation)**2))+(Kxx*(math.sin(rotation)**2)),P)) #Kii
                        rows.append(round((Kyy-Kxx)*math.sin(rotation)*math.cos(rotation),P)) #Kij
                        rows.append(round((Kxx*(math.cos(rotation)**2))+(Kyy*(math.sin(rotation)**2)),P)) #Kjj

                    fet.setGeometry(feature.geometry())
                    fet.setAttributes(rows)
                    writer.addFeature(fet, QgsFeatureSink.FastInsert)

                else:
                    rows = {idxs[0]:round(Kxx,P),idxs[1]:round(Kxy,P),idxs[2]:round(Kyy,P),idxs[3]:round(K1a,P),idxs[4]:round(K1,P),idxs[5]:round(K2,P),idxs[6]:round(K12,P)}
                    if rotation > 0:
                        rows[idxs[7]] = round((Kyy*(math.cos(rotation)**2))+(Kxx*(math.sin(rotation)**2)),P) #Kii
                        rows[idxs[8]] = round((Kyy-Kxx)*math.sin(rotation)*math.cos(rotation),P) #Kij
                        rows[idxs[9]] = round((Kxx*(math.cos(rotation)**2))+(Kyy*(math.sin(rotation)**2)),P) #Kjj
                    pr.changeAttributeValues({feature.id():rows})

            except Exception as e:
                feedback.reportError(QCoreApplication.translate('Error',str(e)))
                continue

        if self.Output in parameters:
            return {self.Output: dest_id}
        else:
            TP.commitChanges()
            return {}
