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
import pandas as pd
import numpy as np

def main (data,bins):

    try:
        df = pd.read_csv(data,header=None,sep=':')
        os.remove(data)

        for n,g in df.groupby(0):
            fig = plt.figure('%s'%(n))
            counts, bins2 = np.histogram(g[1], bins=eval(bins), range=(0, max(g[1])))
            bins2 = list(bins2)
            bins2.append(max(bins2)+bins2[1])
            ax = g[1].hist(bins=bins2,color = '0.75')
            ax.set_xlabel('Bins')
            ax.set_ylabel('Frequency')
            #ax.set_xticks(bins2)
            
            ax.set_ylim(0,max(counts)+1)
            ax.set_xlim(0,bins2[-1])
            plt.title('Histogram Distribution')
            
            info = g[1].describe()
            row_labels = list(info.index)
            table_vals = [[round(x,2)] for x in list(info)]
            table = plt.table(colWidths = [0.2], cellText=table_vals,rowLabels=row_labels,colLabels=['Summary'],loc='upper right')
            #table.set_fontsize(15)
            #table.scale(1.2, 1.2)

            x,y = max(g[1])*0.75, len(g[1])*0.75
            plt.show()
        
    except Exception,e:
        print e
        time.sleep(10)

if __name__ == "__main__":        
    ###Inputs###
        
    inFC = sys.argv[1]
    bins = sys.argv[2]

    main(inFC,bins)

