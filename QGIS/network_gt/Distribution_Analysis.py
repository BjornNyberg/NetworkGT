import math,os
import numpy as np
import pandas as pd
import processing as st
from scipy.stats import norm,lognorm,mstats,kurtosis,skew

import plotly.graph_objs as go
import plotly.plotly as py
import plotly

from qgis.PyQt.QtCore import QCoreApplication, QVariant

from qgis.core import (edit,QgsField, QgsFeature, QgsPointXY,QgsProcessingParameterBoolean, QgsProcessingParameterNumber,
QgsProcessing,QgsWkbTypes, QgsGeometry, QgsProcessingAlgorithm, QgsProcessingParameterFeatureSource,QgsWkbTypes,QgsFeatureSink,
QgsProcessingParameterNumber,QgsFeatureRequest,QgsFields,QgsProperty,QgsVectorLayer,QgsProcessingParameterFeatureSink,QgsProcessingParameterField)

from qgis.PyQt.QtGui import QIcon

class DistributionAnalysis(QgsProcessingAlgorithm):

    Network = 'Network'
    Length = 'Weight'
    
    def __init__(self):
        super().__init__()
        
    def name(self):
        return "Distribution Analysis"

    def tr(self, text):
        return QCoreApplication.translate("Distribution Analysis", text)

    def displayName(self):
        return self.tr("Distribution Analysis")
 
    def group(self):
        return self.tr("Geometry")
    
    def shortHelpString(self):
        return self.tr("Distribution analysis of a fracture network")

    def groupId(self):
        return "Geometry"
    
    def helpUrl(self):
        return "https://github.com/BjornNyberg/NetworkGT/blob/master/QGIS/README.pdf"
    
    def createInstance(self):
        return type(self)()

    def icon(self):
        pluginPath = os.path.join(os.path.dirname(__file__),'icons')
        return QIcon( os.path.join( pluginPath, 'DA.jpg') )
    
    def initAlgorithm(self, config):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.Network,
            self.tr("Fracture Network"),
            [QgsProcessing.TypeVectorLine]))
        self.addParameter(QgsProcessingParameterField(self.Length,
            self.tr('Weight Field'), parentLayerParameterName=self.Network, type=QgsProcessingParameterField.Numeric,optional=True))

    def processAlgorithm(self, parameters, context, feedback):
            
        Network = self.parameterAsSource(parameters, self.Network, context)   
        group = self.parameterAsString(parameters, self.Length, context)
        
     
        SN = []
        LEN = []
        fc_count = Network.featureCount()
        total = 100.0/float(fc_count)

        for feature in Network.getFeatures():
            SN.append(feature.id())
            if group:
                LEN.append(feature[group])
            else:
                LEN.append(feature.geometry().length())
        
        df = pd.DataFrame({'Sample No.':SN, 'LEN':LEN})
        df.set_index('Sample No.')
        df.sort_values(by='LEN',ascending=False,inplace=True)
        df_idx = np.arange(1,len(df)+1)
        
        df['Cum_Freq'] = df_idx/float(len(df))*100.0
        df['CF_NL'] = np.log(df['Cum_Freq'])
        df['LEN_NL'] = np.log(df['LEN'])
        gmean = mstats.gmean(df['LEN'])/100.000000001
        std = df['LEN'].std()/100.000000001
        df['NSD']=norm.ppf(df['Cum_Freq']/100.00000000001,loc=gmean,scale=std)/std

        std = np.std(np.log(df['Cum_Freq']))
        mean = np.mean(std)
        
        df['LNSD'] = (np.log(lognorm(mean,scale=np.exp(std)).ppf(df['Cum_Freq']/100.00000000001))-mean)/std
            
        samples = df.index.tolist()

        info = df['LEN'].describe()
        labels = ['geom mean','CoV','skewness','kurtosis']
        vals = [gmean*100.000000001,np.std(df['LEN'])/np.mean(df['LEN']),skew(df['LEN']),kurtosis(df['LEN'])]

        feedback.pushInfo(QCoreApplication.translate('Distribution Analysis',' Summary Statistics'))
        for k,v in info.items():
            feedback.pushInfo(QCoreApplication.translate('Distribution Analysis','%s %s'%(k,v)))
        for l,v in zip(labels,vals):
            feedback.pushInfo(QCoreApplication.translate('Distribution Analysis','%s %s'%(l,v)))

        trace1 = go.Scatter(x=df['LEN'], y=df['Cum_Freq'])
        trace2 = go.Scatter(x=df['LEN'], y=df['CF_NL'])
        trace3 = go.Scatter(x=df['LEN_NL'], y=df['CF_NL'])
        trace4 = go.Scatter(x=df['LEN'], y=df['NSD'])
        trace5 = go.Scatter(x=df['LEN_NL'], y=df['NSD'])
                            

        fig = plotly.tools.make_subplots(rows=2, cols=3, specs=[[{}, {},{}],
           [{},{}, None]],subplot_titles=('Cumulative Frequency', '-ve expotential',
                                                          'Power-law', 'Normal SD','Log Normal SD'))

        fig.append_trace(trace1, 1, 1)
        fig.append_trace(trace2, 1, 2)
        fig.append_trace(trace3, 1, 3)
        fig.append_trace(trace4, 2, 1)
        fig.append_trace(trace5, 2, 2)

        plotly.offline.plot(fig)
        
        return {}
