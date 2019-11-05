import math,os
import numpy as np
import pandas as pd
import processing as st
from scipy.stats import norm,lognorm,mstats,kurtosis,skew

from qgis.PyQt.QtCore import QCoreApplication, QVariant

from qgis.core import (edit,QgsField, QgsFeature, QgsPointXY,QgsProcessingParameterBoolean, QgsProcessingParameterNumber,
QgsProcessing,QgsWkbTypes, QgsGeometry, QgsProcessingAlgorithm, QgsProcessingParameterFeatureSource,QgsWkbTypes,QgsFeatureSink,
QgsProcessingParameterNumber,QgsFeatureRequest,QgsFields,QgsProperty,QgsVectorLayer,QgsProcessingParameterFeatureSink,QgsProcessingParameterField)

from qgis.PyQt.QtGui import QIcon

class DistributionAnalysis(QgsProcessingAlgorithm):

    Network = 'Network'
    DA = 'Distribution Analysis'
    Length = 'Length'
    
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
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.DA,
            self.tr("Distribution Analysis"),
            QgsProcessing.TypeVectorLine))
        self.addParameter(QgsProcessingParameterField(self.Length,
            self.tr('Weight Field'), parentLayerParameterName=self.Network, type=QgsProcessingParameterField.Numeric))

    def processAlgorithm(self, parameters, context, feedback):
            
        Network = self.parameterAsSource(parameters, self.Network, context)   
        group = self.parameterAsString(parameters, self.Length, context)
        
        fs = QgsFields()
        f_name = ['LEN','Cum_Freq','NSD','LNSD']
        for f in f_name:        
            fs.append(QgsField(f, QVariant.Double))
        (writer, dest_id) = self.parameterAsSink(parameters, self.DA, context,
                                               fs, QgsWkbTypes.LineString, Network.sourceCrs())
        SN = []
        LEN = []
        fc_count = Network.featureCount()
        total = 100.0/float(fc_count)
        feedback.pushInfo(QCoreApplication.translate('Distribution Analysis','Reading Fracture Lines'))
        for feature in Network.getFeatures():
            SN.append(feature.id())
            LEN.append(feature[group])
        
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

        feedback.pushInfo(QCoreApplication.translate('Distribution Analysis','Creating Data'))
        fet = QgsFeature()
        for enum,feature in enumerate(Network.getFeatures()):
            feedback.setProgress(int(enum*total))  
            if feature.id() in samples:
                data = df.iloc[feature.id()]
                rows = []   
                for f in f_name:
                    rows.append(float(data[f]))
                fet.setGeometry(feature.geometry())
                fet.setAttributes(rows)
                writer.addFeature(fet,QgsFeatureSink.FastInsert)


        info = df['LEN'].describe()
        labels = ['geom mean','CoV','skewness','kurtosis']
        vals = [gmean*100.000000001,np.std(df['LEN'])/np.mean(df['LEN']),skew(df['LEN']),kurtosis(df['LEN'])]
        feedback.pushInfo(QCoreApplication.translate('Distribution Analysis','%s'%(info)))

        for l,v in zip(labels,vals):
            feedback.pushInfo(QCoreApplication.translate('Distribution Analysis','%s %s'%(l,v)))
            
        
        return {self.DA:dest_id}
