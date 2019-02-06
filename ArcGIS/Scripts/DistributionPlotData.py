#==================================
#Author Bjorn Burr Nyberg 
#University of Bergen
#Contact bjorn.nyberg@uib.no
#Copyright 2016
#==================================

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


import  sys,time,os
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import norm,lognorm,mstats,skew,kurtosis

import warnings
warnings.simplefilter(action = "ignore", category = FutureWarning)

def main (data_v):

    try:
        data = pd.read_csv(data_v,header=None,sep=':')
        os.remove(data_v)

        for n,df in data.groupby(1):
            if len(df) > 1:
 
                df0 = df[0].sort_values(ascending=False)
                df.index = range(1,len(df0)+1)
                
                df1 = df.index/float(len(df))*100.0
                
                gmean = mstats.gmean(df0)/100.000000001
                std = df0.std()/100.000000001
                df2 = norm.ppf(df1/100.00000000001,loc=gmean,scale=std)/std

                std = np.std(np.log(df1))
                mean = np.mean(std)
                
                df3 = (np.log(lognorm(mean,scale=np.exp(std)).ppf(df1/100.00000000001))-mean)/std

                fig = plt.figure('%s'%(n))
                ax1 = fig.add_subplot(2,3,1)
                ax1.scatter(df0,df1,marker="o",color="0.7")
                ax1.set_ylim([0,max(df1)])
                ax1.set_xlim([0,max(df0)])
                ax1.set_title('Cumulative Frequency')
                ax1.set_xlabel('Size')
                ax1.set_ylabel('% N')
                
                ax2 = fig.add_subplot(2,3,2)
                ax2.scatter(df0,df1,marker="o",color="0.7")
                ax2.set_yscale('log')
                ax2.set_ylim([0,max(df1)])
                ax2.set_xlim([0,max(df0)])
                ax2.set_title('-ve expotential')
                ax2.set_xlabel('Size')
                ax2.set_ylabel('% N')
                
                ax3 = fig.add_subplot(2,3,3)
                ax3.scatter(df0,df1,marker="o",color="0.7")
                ax3.set_yscale('log')
                ax3.set_xscale('log')
                ax3.set_ylim([0,max(df1)])
                ax3.set_xlim([0,max(df0)])
                ax3.set_title('Power-law')
                ax3.set_xlabel('Size')
                ax3.set_ylabel('% N')

                ax4 = fig.add_subplot(2,3,5)
                ax4.scatter(df0,df2,marker="o",color="0.7")
                ax4.set_ylim([min(df2),max(df2[:-1])])
                ax4.set_xlim([0,max(df0)])
                ax4.set_title('Normal SD')
                ax4.set_xlabel('Size')
                ax4.set_ylabel('SD')

                ax5 = fig.add_subplot(2,3,6)
                ax5.scatter(df0,df3,marker="o",color="0.7")
                ax5.set_xscale('log')
                ax5.set_ylim([min(df3),max(df3[:-1])])
                ax5.set_xlim([0,max(df0)])
                ax5.set_title('Log normal SD')
                ax5.set_xlabel('Size')
                ax5.set_ylabel('SD')

                ax6 = fig.add_subplot(2,3,4)
                ax6.axis('tight')
                ax6.axis('off')
                info = df0.describe()
                col_labels = ['Summary']
                row_labels = list(info.index)
                row_labels.extend(['geom mean','CoV','skewness','kurtosis'])  

                table_vals = [[round(x,2)] for x in list(info)]
                add_vals = [gmean*100.000000001,np.std(df0)/np.mean(df0),skew(df0),kurtosis(df0)]
                table_vals.extend([[round(a,2)] for a in add_vals])
                table = plt.table(colWidths = [0.7],cellText=table_vals,rowLabels=row_labels,colLabels=col_labels,loc='center',cellLoc='center')
   
                plt.show()
		
    except Exception,e:
        print e
        time.sleep(10)

if __name__ == "__main__":        
    ###Inputs###
        
    data = sys.argv[1]

    main(data)

