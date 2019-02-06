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
    
import os, sys, numpy
import pandas as pd
import processing as st

from qgis.PyQt.QtCore import QCoreApplication, QVariant

from qgis.core import (edit,QgsField, QgsFeature, QgsPointXY,QgsProcessingParameterBoolean, QgsProcessingParameterNumber,
QgsProcessing,QgsWkbTypes, QgsGeometry, QgsProcessingAlgorithm, QgsProcessingParameterFeatureSource,QgsWkbTypes,QgsFeatureSink,
QgsProcessingParameterNumber,QgsFeatureRequest,QgsFields,QgsProperty,QgsVectorLayer,QgsProcessingParameterFeatureSink)


class TopologyParameters(QgsProcessingAlgorithm):

    Sample_Area = 'Sample Area'
    Nodes = 'Nodes'
    Branches = 'Branches'
    TP = "Topology Parameters"
    
    def __init__(self):
        super().__init__()
        
    def name(self):
        return "Topology Parameters"

    def tr(self, text):
        return QCoreApplication.translate("Topology Parameters", text)

    def displayName(self):
        return self.tr("Topology Parameters")
 
    def group(self):
        return self.tr("NetworkGT")
    
    def shortHelpString(self):
        return self.tr("Define topological parameters for a given sample area")

    def groupId(self):
        return "Topology"
    
    def helpUrl(self):
        return "https://github.com/BjornNyberg/NetworkGT"
    
    def createInstance(self):
        return type(self)()
    
    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.Nodes,
            self.tr("Nodes"),
            [QgsProcessing.TypeVectorPoint]))
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.Branches,
            self.tr("Branches"),
            [QgsProcessing.TypeVectorLine]))
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.Sample_Area,
            self.tr("SampleArea"),
            [QgsProcessing.TypeVectorPolygon]))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.TP,
            self.tr("Topology Parameters"),
            QgsProcessing.TypeVectorPolygon))

    def processAlgorithm(self, parameters, context, feedback):
            
        Nodes = self.parameterAsSource(parameters, self.Nodes, context)
        Branches = self.parameterAsSource(parameters, self.Branches, context)
        SA = self.parameterAsSource(parameters, self.Sample_Area, context)
        layer  = self.parameterAsVectorLayer(parameters, self.Sample_Area, context)
        
        feedback.pushInfo(QCoreApplication.translate('TopologyParameters','Reading Data'))
        
        SN = []
        CLASS = []
        
        for feature in Nodes.getFeatures(QgsFeatureRequest()):
            SN.append(feature['Sample_No_'])
            CLASS.append(feature['Class'])
                      
        df = pd.DataFrame({'Sample No.':SN, 'Class':CLASS})

        df['Nodes'] = 0
        
        df = df[['Sample No.','Class','Nodes']].groupby(['Sample No.','Class']).count().unstack(level=1)

        df.fillna(0,inplace=True)
        df.columns = df.columns.droplevel()

        node_columns = ['I','X','Y','E', 'U']

        for column in node_columns:
            if column not in df:
                df[column] = 0.0

        if 'Error' in df:  
            del df['Error']

        df['No. Nodes'] = df.X + df.Y + df.I
        df['No. Branches'] = ((df.X*4.0) + (df.Y*3.0) + df.I)/2.0
        df['No. Lines'] = (df.Y + df.I)/2
        df['No. Connections'] = df.X + df.Y
        df['Connect/Line'] = (2.0*(df.X+df.Y))/df['No. Lines']

        SN = []
        B = []
        CON = []
        LEN = []
                      
        for feature in Branches.getFeatures(QgsFeatureRequest()):
            SN.append(feature['Sample_No_'])
            B.append(feature['Weight'])
            CON.append(feature['Connection'])
            LEN.append(feature.geometry().length())

        df2 = pd.DataFrame({'Sample No.':SN, 'Branches':B, 'Connection':CON,'Length':LEN})
        df3 = df2[['Sample No.','Branches','Connection']].groupby(['Sample No.','Connection']).sum().unstack(level=1)
        
        df3.fillna(0.0,inplace=True)

        df3.columns = df3.columns.droplevel()

        branch_columns = ['C - C','C - I', 'C - U','I - I','I - U','U - U']
        delete_columns = ['C - Error','Error - Error','Error - I', 'Error - U']

        for column in branch_columns:
            if column not in df3:
                df3[column] = 0.0

        for column in delete_columns:
            if column in df3:
                del df3[column]
        
        df3['No. Branches'] = df3['C - C'] + df3['C - I'] + df3['I - I'] + df3['C - U'] + df3['I - U'] + df3['U - U']

        df2 = df2[['Sample No.','Length','Connection']].groupby(['Sample No.','Connection']).sum().unstack(level=1)
        df2.fillna(0.0,inplace=True)
        df2.columns = df2.columns.droplevel()

        for column in branch_columns:
            if column not in df2:
                df2[column] = 0.0
                
        for column in delete_columns:
            if column in df2:
                del df2[column]

        df2['Total Trace Length'] = df2['C - C'] + df2['C - I'] + df2['I - I'] + df2['C - U'] + df2['I - U'] + df2['U - U']
        
        check = SA.fields().indexFromName('Radius')
        
        SN = []
        CIRC = []
        AREA = []
        fet = QgsFeature() 
        
        for feature in SA.getFeatures(QgsFeatureRequest()):
            SN.append(feature['Sample_No_'])
            if check == -1:
                CIRC.append(feature.geometry().length())
                AREA.append(feature.geometry().area())
            else:
                CIRC.append(feature['Circumfere'])
                AREA.append(feature['Area'])
            
        df4 = pd.DataFrame({'Sample No.':SN, 'Circumference':CIRC, 'Area':AREA})
                      
        df4.set_index('Sample No.', inplace=True)

        df['Average Line Length'] = df2['Total Trace Length'] / df['No. Lines']
        df['Average Branch Length'] = df2['Total Trace Length'] / df['No. Branches']
        df['Connect/Branch'] = ((3.0*df.Y) + (4.0*df.X)) / df['No. Branches']
        df['Branch Freq'] = df['No. Branches'] / df4['Area']
        df['Line Freq'] = df['No. Lines'] / df4['Area']
        df['NcFreq'] = df['No. Connections'] / df4['Area']
        samples = df.index.tolist()
        
        df4 = df4.ix[samples]
                      
        r = df4['Circumference']/(numpy.pi*2.0)

        a = numpy.pi*r*r
        a = df4['Area'] - a
        df['a'] = numpy.fabs(a.round(4))

        df['1D Intensity'] = 0.0

        df.ix[df.a==0.0,'1D Intensity'] = (df['E'] /(2.0*numpy.pi*r)) *(numpy.pi/2.0)
        del df['a']
        
        df['2D Intensity'] =  df2['Total Trace Length'] / df4['Area']
        df['Dimensionless Intensity'] = df['2D Intensity'] * df['Average Branch Length']
        
        df = pd.concat([df4,df,df3,df2],axis=1)

        df = df[numpy.isfinite(df['No. Nodes'])]
        df.replace(numpy.inf, 0.0,inplace=True)
        df.replace(numpy.nan, 0.0,inplace=True)
        df = df.round(5)

        fs = QgsFields()
        
        i = [0,3,4,5,6,7,8,9,10,11,22,23,24,25,26,27]
        for enum,c in enumerate(df):
            if enum in i:
                fs.append(QgsField(c, QVariant.Int))
            else:
                fs.append(QgsField(c, QVariant.Double))

        (writer, dest_id) = self.parameterAsSink(parameters, self.TP, context,
                                            fs, QgsWkbTypes.Polygon, Nodes.sourceCrs())

        field_check = SA.fields().indexFromName('Set')
        if field_check == -1:
            provider = layer.dataProvider()
            provider.addAttributes([QgsField('Set', QVariant.Int),QgsField('Orient', QVariant.Double)])
            layer.updateFields() 
            
        feedback.pushInfo(QCoreApplication.translate('TopologyParametersOutput','Creating Output'))
        
        for feature in SA.getFeatures(QgsFeatureRequest()):
            if feature['Sample_No_'] in samples:
                fet.setGeometry(feature.geometry())
                fet.setAttributes(df.ix[feature['Sample_No_']].tolist())
                writer.addFeature(fet,QgsFeatureSink.FastInsert)  

        return {self.TP:dest_id}
