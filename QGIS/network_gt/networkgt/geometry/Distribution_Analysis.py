import os
from qgis.PyQt.QtCore import QCoreApplication

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
        return self.tr("3. Geometry")

    def shortHelpString(self):
        return self.tr("Plots cumulative line frequency against fracture size (e.g. length, aperture, displacement). Several line plots are produced with variable axis scales to help the user interpet the frequency-size distribution (e.g. negative exponential, power-law, normal, log-normal). \n The input data needs to be a fracture network linestring and the various line plots are externally output in a browser window. Additionally a number of statistics (max, min, mean, standard deviation, coefficent of variance etc.) are calculated and displayed within the tool log.  \n N.B. The weight field will default to fracture length if not supplied.\n Please refer to the help button for more information.")

    def groupId(self):
        return "3. Geometry"

    def helpUrl(self):
        return "https://github.com/BjornNyberg/NetworkGT/wiki/3.-Geometry-Analysis"

    def createInstance(self):
        return type(self)()

    def icon(self):
        n,path = 2,os.path.dirname(__file__)
        while(n):
            path=os.path.dirname(path)
            n -=1
        pluginPath = os.path.join(path,'icons')
        return QIcon( os.path.join( pluginPath, 'DA.jpg') )

    def initAlgorithm(self, config):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.Network,
            self.tr("Fracture Network"),
            [QgsProcessing.TypeVectorLine]))
        self.addParameter(QgsProcessingParameterField(self.Length,
            self.tr('Weight Field'), parentLayerParameterName=self.Network, type=QgsProcessingParameterField.Numeric,optional=True))

    def processAlgorithm(self, parameters, context, feedback):

        try:
            import pandas as pd
            import numpy as np
            from scipy.stats import norm,lognorm,mstats,kurtosis,skew
            import plotly.graph_objs as go
            import chart_studio.plotly as py
        except Exception as e:
            feedback.reportError(QCoreApplication.translate('Error','%s'%(e)))
            feedback.reportError(QCoreApplication.translate('Error',' '))
            feedback.reportError(QCoreApplication.translate('Error','Error loading modules - please install the necessary dependencies'))
            return {}

        Network = self.parameterAsLayer(parameters, self.Network, context)
        group = self.parameterAsString(parameters, self.Length, context)

        SN = []
        LEN = []
        #fc_count = Network.featureCount()

        features = Network.selectedFeatures()
        if len(features) == 0:
            features = Network.getFeatures()

        for feature in features:
            SN.append(feature.id())
            if group:
                L = feature[group]
                if type(L) == int or type(L) == float:
                    pass
                else:
                    feedback.reportError(QCoreApplication.translate('Error','Weight field contains non numeric values - check for null values'))
                LEN.append(L)
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

       # samples = df.index.tolist()

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
      #  maxSD = df['LEN'].tolist()[-2]
        ngtPath = 'https://raw.githubusercontent.com/BjornNyberg/NetworkGT/master/Images/NetworkGT_Logo1.png'
        layout = go.Layout(images=[dict(source=ngtPath,xref="paper", yref="paper", x=1.0, y=1.0,sizex=0.2, sizey=0.2, xanchor="right", yanchor="bottom")],
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

        fig = go.Figure([trace2, trace3, trace4, trace5], layout=layout)
        try:
            py.plot(fig, filename='Distribution Analysis', auto_open=True)
        except Exception:
            fig.show()
        return {}
