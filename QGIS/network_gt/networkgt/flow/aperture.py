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

from qgis.core import (edit,QgsField, QgsFeature, QgsPointXY,QgsProcessingParameterBoolean, QgsProcessingParameterNumber,QgsProcessingParameterEnum,
QgsProcessing,QgsWkbTypes, QgsGeometry, QgsProcessingAlgorithm, QgsProcessingParameterFeatureSource,QgsWkbTypes,QgsFeatureSink,
QgsProcessingParameterNumber,QgsFeatureRequest,QgsFields,QgsProperty,QgsVectorLayer,QgsProcessingParameterFeatureSink,QgsProcessingParameterField)

from qgis.PyQt.QtGui import QIcon

class Aperture(QgsProcessingAlgorithm):

    Network = "Fracture Network"
    const = 'Constant Aperture'
    Method = 'Method'
    C = 'C'
    FP = 'Fracture Porosity'
    Group = 'Group'

    def __init__(self):
        super().__init__()

    def name(self):
        return "Aperture"

    def tr(self, text):
        return QCoreApplication.translate("Aperture", text)

    def displayName(self):
        return self.tr("Aperture")

    def group(self):
        return self.tr("5. Flow")

    def shortHelpString(self):
        return self.tr("Defines the maximum and average aperture of a fracture trace, based on a relationship between maximum aperture (A) and fracture length (L) whereby A = C.L^0.5.  The user can supply a field to sum the fracture length based on specified fracture ID. The user can also vary the coefficient C, which is related to the material properties of the host rock and generally ranges between 10-2 and 10-5. Alternatively, the user can define a constant aperture for all fractures within the network. In addition, the aperture is combined with a user specified fracture porosity (ranging from 0-1) to calculate the intrinsic permeability (millidarcy's; mD) and transmisivity (mD.m) of the fractures. \n The input is a fracture network linestring and the calculated parameters are added to its attribute table. \n N.B. Units of aperture and length must be given in m.\n Please refer to the help button for more information.")

    def groupId(self):
        return "5. Flow"

    def helpUrl(self):
        return "https://github.com/BjornNyberg/NetworkGT/wiki/5.-Flow-Assessment"

    def createInstance(self):
        return type(self)()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.Network,
            self.tr("Fracture Network"),
            [QgsProcessing.TypeVectorLine]))

        self.addParameter(QgsProcessingParameterEnum(self.Method,
                                self.tr('Aperture Field for Transmisivity'), options=[self.tr("Average"),self.tr("Max"),self.tr("Constant")],defaultValue=0))

        self.addParameter(QgsProcessingParameterField(self.Group,
                                self.tr('Group Fracture Length By'), parentLayerParameterName=self.Network, type=QgsProcessingParameterField.Any, optional=True))

        self.addParameter(QgsProcessingParameterNumber(
            self.C,
            self.tr("C Value"),
            QgsProcessingParameterNumber.Double,
            0.01,
            minValue=0.00001,
            maxValue=0.1))

        self.addParameter(QgsProcessingParameterNumber(
            self.FP,
            self.tr("Fracture Porosity"),
            QgsProcessingParameterNumber.Double,
            1.0,
            minValue=0,
            maxValue=1))

        self.addParameter(QgsProcessingParameterNumber(
            self.const,
            self.tr("Apply a constant aperture"),
            QgsProcessingParameterNumber.Double,
            0.0, optional=True))

    def processAlgorithm(self, parameters, context, feedback):

        Network = self.parameterAsLayer(parameters, self.Network, context)
        c = parameters[self.C]
        fp = parameters[self.FP]
        const = parameters[self.const]
        m = parameters[self.Method]
        grp = parameters[self.Group]

        pr = Network.dataProvider()

        if const > 0:
            new_fields = ['maxA','avgA','Aperture','IntrinsicP','Transmisiv']
        else:
            if const == 0 and m == 2:
                feedback.reportError(QCoreApplication.translate('Output','Can not calculate transmisivity based on a constant aperture of 0'))
                return {}
            new_fields = ['maxA','avgA','IntrinsicP','Transmisiv']

        if grp:
            new_fields.append('Fault Len')

        for field in new_fields:
            if Network.fields().indexFromName(field) == -1:
                pr.addAttributes([QgsField(field, QVariant.Double)])

        Network.updateFields()
        idxs = []
        for field in new_fields:
            idxs.append(Network.fields().indexFromName(field))

        field_check = Network.fields().indexFromName('origLen')
        if field_check != -1:
            feedback.reportError(QCoreApplication.translate('Info','Warning: Applying the origLen field to calculate fracture length'))

        features = list(Network.selectedFeatures())
        total = Network.selectedFeatureCount()
        if len(features) == 0:
            features = list(Network.getFeatures())
            total = Network.featureCount()
        total = 100.0/total

        if grp:
            feedback.pushInfo(QCoreApplication.translate('Output','Grouping Fracture Lengths'))
            data = {}
            for enum,feature in enumerate(features):
                if total > 0:
                    feedback.setProgress(int(enum*total))
                FID = feature[grp]
                if field_check != -1:
                    fLen = feature['origLen']
                else:
                    fLen = feature.geometry().length()
                if type(fLen) != float:
                    feedback.reportError(QCoreApplication.translate('Info','Warning: Fracture length field contains non-float values'))
                    return {}
                if FID not in data:
                    data[FID] = fLen
                else:
                    data[FID] += fLen

        feedback.pushInfo(QCoreApplication.translate('Output','Updating Aperture Field'))
        Network.startEditing()
        for enum,feature in enumerate(features):
            if total > 0:
                feedback.setProgress(int(enum*total))
            if grp:
                fLen = data[feature[grp]]
            else:
                if field_check != -1:
                    fLen = feature['origLen']
                else:
                    fLen = feature.geometry().length()
            if type(fLen) != float:
                feedback.reportError(QCoreApplication.translate('Info','Warning: Fracture length field contains non-float values'))
                return {}
            maxA = c*(fLen**0.5)
            avgA = math.sqrt((((math.pi*c)**2)*fLen)/16)

            if const > 0:
                a = const
            elif m == 0:
                a = avgA
            else:
                a = maxA

            iP =(((a**2)/12)*fp)/9.869233E-16
            t = iP*a

            if const > 0:
                rows = {idxs[0]:maxA,idxs[1]:avgA,idxs[2]:const,idxs[3]:iP,idxs[4]:t}
            else:
                rows = {idxs[0]:maxA,idxs[1]:avgA,idxs[2]:iP,idxs[3]:t}

            if grp:
                rows[idxs[-1]] = fLen

            pr.changeAttributeValues({feature.id():rows})

        Network.commitChanges()

        return {}
