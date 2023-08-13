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

import os, math, string,random, tempfile
from qgis.PyQt.QtCore import QCoreApplication, QVariant

from qgis.core import (edit,QgsField, QgsFeature, QgsPointXY,QgsProcessingParameterBoolean, QgsProcessingParameterNumber,
QgsProcessing,QgsWkbTypes, QgsGeometry, QgsProcessingAlgorithm, QgsProcessingParameterFeatureSource,QgsWkbTypes,QgsFeatureSink,
QgsProcessingParameterNumber,QgsFeatureRequest,QgsFields,QgsProperty,QgsVectorLayer,QgsProcessingParameterFeatureSink)

from qgis.PyQt.QtGui import QIcon

class Percolation(QgsProcessingAlgorithm):

    TP = "Topology Parameters"
    CV = "CV"
    Output = 'Output'
    Plot = 'Plot'

    def __init__(self):
        super().__init__()

    def name(self):
        return "Percolation"

    def tr(self, text):
        return QCoreApplication.translate("Percolation", text)

    def displayName(self):
        return self.tr("Percolation")

    def group(self):
        return self.tr("5. Flow")

    def shortHelpString(self):
        return self.tr("Defines the percolation threshold for a given sample area as a critical dimensionless intensity (B22C). Expected values for B22C can be derived for any network topology and are defined for four fracture orientation cases: 1) randomly orientated fractures; 2) orthognal fractures; 3) conjugate (60 degree) fractures; 4) oblique (30 degree) fractures. The user has the option to adjust the values of B22C and B22 based on the branch length variation, defined as the coefficient of variance (CV). \n The input is a topology parameters polygon/contour grid and derived values are added to its attribute table. Additionally the dimensionless intensity (B22) of the sample area is plotted against the B22C on a scatter plot to hekp the user visualise if a network is above, below or at the percolation threshold.\n Please refer to the help button for more information.")

    def groupId(self):
        return "5. Flow"

    def helpUrl(self):
        return "https://github.com/BjornNyberg/NetworkGT/wiki/5.-Flow-Assessment"

    def createInstance(self):
        return type(self)()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.TP,
            self.tr("Topology Parameters"),
            [QgsProcessing.TypeVectorPolygon]))

        self.addParameter(QgsProcessingParameterNumber(
            self.CV,
            self.tr("Branch Length Variance (CV)"),
            QgsProcessingParameterNumber.Double,
            0.0,
            minValue=0.0))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.Output,
            self.tr("Percolation"),
            QgsProcessing.TypeVectorPolygon, '',optional=True))
        self.addParameter(QgsProcessingParameterBoolean(self.Plot,
                    self.tr("Plot"),False))

    def processAlgorithm(self, parameters, context, feedback):

        plot = parameters[self.Plot]

        try:
            import plotly.graph_objs as go
            import chart_studio.plotly as py
        except Exception:
            feedback.reportError(QCoreApplication.translate('Error','Plotting will be disabled as plotly module did not load - please install the necessary dependencies.'))
            plot = False

        TP = self.parameterAsLayer(parameters, self.TP, context)
        CV = parameters[self.CV]

        if TP.fields().indexFromName('I') == -1:
            feedback.reportError(QCoreApplication.translate('Error','Topology Parameters input is invalid - please run the topology parameters tool prior to calulcating percolation'))
            return {}

        new_fields = ['B22', 'B22c-R', 'B22c-O', 'B22c-30', 'B22c-60']

        if self.Output in parameters:
            fields = QgsFields()
            for field in TP.fields():
                if field.name() not in new_fields:
                    fields.append(QgsField(field.name(), field.type()))

            for field in new_fields:
                fields.append(QgsField(field, QVariant.Double))

            (writer, dest_id) = self.parameterAsSink(parameters, self.Output, context,
                                                     fields, QgsWkbTypes.Polygon, TP.sourceCrs())
            fet = QgsFeature()
        else:
            pr = TP.dataProvider()
            for field in new_fields:
                if TP.fields().indexFromName(field) == -1:
                    pr.addAttributes([QgsField(field, QVariant.Double)])
            TP.updateFields()
            idxs = []
            for field in new_fields:
                idxs.append(TP.fields().indexFromName(field))
            TP.startEditing()

        feedback.pushInfo(QCoreApplication.translate('TopologyParametersOutput','Calculating Percolation'))

        samples = []
        B,R,O,a60,a30 = [],[],[],[],[]

        features = TP.selectedFeatures()
        total = TP.selectedFeatureCount()
        if len(features) == 0:
            features = TP.getFeatures()
            total = TP.featureCount()
        total = 100.0/total

        for enum,feature in enumerate(features):
            if total > 0:
                feedback.setProgress(int(enum*total))
            if feature['I'] > 0:
                newL = feature['I'] / 2.0
                if feature['Y'] > 0:
                    Y = feature['Y']/2
                else:
                    Y = 0

                newX = feature['X'] + Y
                newB = ((newX*4) +  feature['I'])/2

                newCL = (2*newX)/newL
                if self.Output in parameters:
                    rows = []
                    for field in TP.fields():
                        if field.name() not in new_fields:
                            rows.append(feature[field.name()])
                try:
                    B22 = (feature['Dimensionl']*(math.sqrt(CV**2+1))) #Shapefile attribute name limit of 10
                except Exception:
                    B22 = (feature['Dimensionless Intensity']*(math.sqrt(CV**2+1)))

                aLog =(newCL-2)/3.7
                if aLog > 0:
                    try:
                        curB = feature['No. Branch']
                    except Exception:
                        curB = feature['No. Branches']

                    a = math.log10(aLog)
                    P22cRC = 5.61*((1.2*(a**2))+(0.64*a)+1)
                    P22cOC = 6.22*((1.2*(a**2))+(0.64*a)+1)
                    P22c60 = P22cOC/(math.sin(math.radians(60)))
                    P22c30 = P22cOC/(math.sin(math.radians(30)))
                    B22cRC = P22cRC/(newB/newL)
                    B22cOC = P22cOC/(newB/newL)
                    B22c60 = P22c60/(newB/newL)
                    B22c30 = P22c30/(newB/newL)
                    B22cR = B22cRC*(newB/curB)*(math.sqrt(CV**2+1))
                    B22cO = B22cOC*(newB/curB)*(math.sqrt(CV**2+1))
                    B22c60V = B22c60*(newB/curB)*(math.sqrt(CV**2+1))
                    B22c30V = B22c30*(newB/curB)*(math.sqrt(CV**2+1))

                    if self.Output in parameters:
                        rows.extend([B22,B22cR,B22cO,B22c30V,B22c60V])
                    else:
                        rows = {idxs[0]:B22,idxs[1]:B22cR,idxs[2]:B22cO,idxs[3]:B22c30V,idxs[4]:B22c60V}

                    n = 'Sample No. %s'%(feature['Sample_No_'])
                    samples.append(n)
                    B.append(B22)
                    R.append(B22cR)
                    O.append(B22cO)
                    a60.append(B22c60V)
                    a30.append(B22c30V)
                else:
                    if self.Output in parameters:
                        rows.extend([-1, -1, -1, -1, -1])
                    else:
                        rows = {idxs[0]:-1,idxs[1]:-1,idxs[2]:-1,idxs[3]:-1,idxs[4]:-1}
            else:
                if self.Output in parameters:
                    rows = []
                    for field in TP.fields():
                        if field.name() not in new_fields:
                            rows.append(feature[field.name()])
                    rows.extend([0, 0, 0, 0, 0])
                else:
                    rows = {idxs[0]:0,idxs[1]:0,idxs[2]:0,idxs[3]:0,idxs[4]:0}
            if self.Output in parameters:
                fet.setGeometry(feature.geometry())
                fet.setAttributes(rows)
                writer.addFeature(fet, QgsFeatureSink.FastInsert)
            else:
                pr.changeAttributeValues({feature.id():rows})
        if not self.Output in parameters:
            TP.commitChanges()

        if plot:
            traces = []

            xmin = min(R)- (min(R)*0.2)
            xmax = max(a30) + (max(a30)*0.2)
            ymin,ymax = xmin,xmax

            if ymin < 0:
                ymin = 0
            if xmin < 0:
                xmin = 0
            if xmax < 10:
                xmin,ymin = 0,0

            lines = [[[0,100],[0,200]],[[0,100],[0,110]],[[0,100],[0,100]],[[0,100],[0,90]],[[0,100],[0,50]]]
            names = ['1:2','1:1.1','1:1','1:0.9','1:0.5']
            for line,n in zip(lines,names):
                if n == '1:1':
                    traces.append(go.Scatter(x = line[0],
                                        y = line[1],
                                        mode = 'lines',
                                        name = '1:1',
                                        line = dict(color='black', width=1.5,)
                                    ))
                else:
                    traces.append(go.Scatter(x = line[0],
                                            y = line[1],
                                            mode = 'lines',
                                            name = n,
                                            line = dict(color='black', width=1, dash='dot')
                                        ))

            traces.append(go.Scatter(y = B, x = R, mode = 'markers', name = 'Random',text=samples,marker = dict(size = 20,color='red')))
            traces.append(go.Scatter(y = B, x = O, mode = 'markers', name = 'Orthogonal',text=samples,marker = dict(size = 20,color='blue')))
            traces.append(go.Scatter(y = B, x = a60, mode = 'markers', name = '60 Degrees',text=samples,marker = dict(size = 20,color='orange')))
            traces.append(go.Scatter(y = B, x = a30, mode = 'markers', name = '30 Degrees',text=samples,marker = dict(size = 20,color='yellow')))

            ngtPath = 'https://raw.githubusercontent.com/BjornNyberg/NetworkGT/master/Images/NetworkGT_Logo1.png'
            layout = dict(images=[dict(source=ngtPath,xref="paper", yref="paper", x=1.0, y=1.0,sizex=0.2, sizey=0.2, xanchor="right", yanchor="bottom")],
                  xaxis = dict(title = 'B22c',range=[xmin, xmax]),
                  yaxis = dict(title = 'B22',range=[ymin, ymax]),
                  )

            fig = go.Figure(data=traces, layout=layout)
            try:
                py.plot(fig, filename='Percolation', auto_open=True)
            except Exception:
                fig.show()

        if self.Output in parameters:
            return {self.Output: dest_id}
        else:
            return {}
