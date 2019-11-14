import math,os,string,random
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
    Export = 'Export SVG File'
    
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
        self.addParameter(QgsProcessingParameterBoolean(self.Export,
                    self.tr("Export SVG File"),False))
    def processAlgorithm(self, parameters, context, feedback):
            
        Network = self.parameterAsSource(parameters, self.Network, context)   
        group = self.parameterAsString(parameters, self.Length, context)
        E = parameters[self.Export]
     
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

        feedback.pushInfo(QCoreApplication.translate('Distribution Analysis','Summary Statistics'))
        for k,v in info.items():
            feedback.pushInfo(QCoreApplication.translate('Distribution Analysis','%s %s'%(k,v)))
        for l,v in zip(labels,vals):
            feedback.pushInfo(QCoreApplication.translate('Distribution Analysis','%s %s'%(l,v)))

        trace2 = go.Scatter(x=df['LEN'], y=df['Cum_Freq'],xaxis='x1',yaxis='y1',name='Negative Exponential')
        trace3 = go.Scatter(x=df['LEN'], y=df['Cum_Freq'],xaxis='x2',yaxis='y2',name='Power-law')
        trace4 = go.Scatter(x=df['LEN'], y=df['NSD'],xaxis='x3',yaxis='y3',name='Normal SD')
        trace5 = go.Scatter(x=df['LEN'], y=df['LNSD'],xaxis='x4',yaxis='y4',name='Log Normal SD')

        maxNSD = df['NSD'].tolist()[-2]
        maxLNSD = df['LNSD'].tolist()[-2]
        maxSD = df['LEN'].tolist()[-2]
        
        layout = go.Layout(
            xaxis=dict(
                title='Size',
                domain=[0, 0.45],
            ),
            yaxis=dict(
                type='log',
                title='% N',
                domain=[0.55, 1.0],
                anchor='x',
                dtick= 1
            ),
            xaxis2=dict(
                    type='log',
                    title='Log Size',
                    domain=[0.55, 1.0],
                    anchor='y2',
                    dtick= 1,   
                ),
            yaxis2=dict(
                    type='log',
                    title='% N',
                    domain=[0.55, 1.0],
                    anchor='x2',
                    dtick= 1
                ),
            xaxis3=dict(
                    title='Size',
                    domain=[0, 0.45],
                    anchor='y3',

                ),
            yaxis3=dict(
                    title='SD',
                    domain=[0, 0.45],
                    anchor='x3',
                    range=[-maxNSD,maxNSD]
                ),
            xaxis4=dict(
                type='log',
                title='Log Size',
                domain=[0.55, 1.0],
                anchor='y4',
                dtick= 1,

            ),
            yaxis4=dict(
                
                title='SD',
                domain=[0, 0.45],
                anchor='x4',
                range=[-maxLNSD,maxLNSD]
            ))

        fig = go.Figure(data=[trace2,trace3,trace4,trace5],layout=layout)
        fname = ''.join(random.choice(string.ascii_lowercase) for i in range(10))
        outDir = os.path.join(os.environ['TMP'],'Plotly')
        if not os.path.exists(outDir):
            os.mkdir(outDir)
        if E:
            fname = os.path.join(outDir,'%s.svg'%(fname))
            plotly.offline.plot(fig,image='svg',filename=fname)
        else:
            fname = os.path.join(outDir,'%s.html'%(fname))
            plotly.offline.plot(fig,filename=fname)
        
        return {}
