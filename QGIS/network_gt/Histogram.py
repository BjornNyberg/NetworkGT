from qgis.PyQt.QtCore import QCoreApplication, QVariant

from qgis.core import (edit,QgsField, QgsFeature, QgsPointXY,QgsProcessingParameterBoolean, QgsProcessingParameterNumber,
QgsProcessing,QgsWkbTypes, QgsGeometry, QgsProcessingAlgorithm, QgsProcessingParameterFeatureSource,QgsWkbTypes,QgsFeatureSink,
QgsProcessingParameterNumber,QgsFeatureRequest,QgsFields,QgsProperty,QgsVectorLayer,QgsProcessingParameterFeatureSink,QgsProcessingParameterField)

from qgis.PyQt.QtGui import QIcon

import plotly.graph_objs as go
import plotly.plotly as py
import plotly,os

class Histogram(QgsProcessingAlgorithm):

    Network = 'Network'
    Group = 'Group Field'
    Weight = 'Weight Field'
    
    def __init__(self):
        super().__init__()
        
    def name(self):
        return "Histogram"

    def tr(self, text):
        return QCoreApplication.translate("Histogram", text)

    def displayName(self):
        return self.tr("Histogram")
 
    def group(self):
        return self.tr("Geometry")
    
    def shortHelpString(self):
        return self.tr("Histogram of a fracture network")

    def groupId(self):
        return "Geometry"
    
    def helpUrl(self):
        return "https://github.com/BjornNyberg/NetworkGT/blob/master/QGIS/README.pdf"
    
    def createInstance(self):
        return type(self)()

    def icon(self):
        pluginPath = os.path.join(os.path.dirname(__file__),'icons')
        return QIcon( os.path.join( pluginPath, 'H.jpg') )
    
    def initAlgorithm(self, config):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.Network,
            self.tr("Fracture Network"),
            [QgsProcessing.TypeVectorLine]))

        self.addParameter(QgsProcessingParameterField(self.Weight,
            self.tr('Weight Field'), parentLayerParameterName=self.Network, type=QgsProcessingParameterField.Numeric,optional=True))

        self.addParameter(QgsProcessingParameterField(self.Group,
            self.tr('Group Field'), parentLayerParameterName=self.Network, type=QgsProcessingParameterField.Numeric,optional=True))

    def processAlgorithm(self, parameters, context, feedback):
            
        Network = self.parameterAsSource(parameters, self.Network, context)
        
        WF = self.parameterAsString(parameters, self.Weight, context)
        G = self.parameterAsString(parameters, self.Group, context)
        
        x = {}
        
        
        for feature in Network.getFeatures():
            if G:
                ID = feature[G]
            else:
                ID = 'Data'
                
            if WF:
                v = feature[WF]
            else:
                v = feature.geometry().length()

            if ID not in x:
                x[ID] = []

            values = x[ID]
            values.append(v)
            x[ID] = values

        traces = []

        for k,v in x.items():
            traces.append(go.Histogram(x=v,name=k))

        layout = go.Layout(barmode='stack')
        fig = go.Figure(data=traces, layout=layout)
        plotly.offline.plot(fig)
        
        return {}
