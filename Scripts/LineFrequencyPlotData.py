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


import sys,time,os,math
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from collections import OrderedDict

def main (data_v):

    try:
        data = pd.read_csv(data_v,header=None,sep=':',na_values = 'None')
        os.remove(data_v)
        data.dropna(inplace=True)
        
        columns = list(data.columns.values)
        
        for n,df in data.groupby(0):

            if len(df) > 1:
                
                fig = plt.figure('Sample # %s'%(n))
                ax = fig.add_subplot(2,1,1)
                data = {}
                vf_values = {}
     
                max_dist = max(df[2])

                x,y,c = [0],[0],0.0
                values = df.sort_values(2)

                prev = 0
                for x_value,disp in zip(values[2],values[3]):
                    y.append(y[-1])
                    c += disp
                    y.append(c)
                    x.extend([x_value,x_value])
                    spacing = [x_value - prev]
                    prev = x_value
                        
                    if 'Total' not in data:
                        data['Total'] = spacing
                            
                    else:
                        spacing_data = data['Total']                            
                        spacing += spacing_data
                        data['Total'] = spacing

                m = float(max(y)/max_dist)

                for x_v,y_v in zip(x,y):
                    test_y = x_v*m
                    vf = [y_v/float(y[-1]) - test_y/y[-1]]
                    if 'Total' in vf_values:
                        vf_data = vf_values['Total']
                        vf_data += vf
                        vf_values['Total'] = vf_data
                    else:
                        vf_values['Total'] = vf
                    
                x.append(max_dist)
                y.append(y[-1])
                ax.plot(x,y,label='Total')

                ylim = max(y)+max(y)*0.1
            
                for n2,g in df.groupby(1):
                    if n2 != 'Total':
                        x,y,c = [0],[0],0.0
                        values = g.sort_values(2)
                        
                        prev = 0
                        for x_value,disp in zip(values[2],values[3]):

                            y.append(y[-1])
                            c += disp
                            y.append(c)
                            x.extend([x_value,x_value])
                            spacing = [x_value - prev]
                            prev = x_value
                            
                            if n2 not in data:
                                data[n2] = spacing
                                
                            else:
                                spacing_data = data[n2]                            
                                spacing += spacing_data
                                data[n2] = spacing
                                
                        m = float(max(y)/max_dist)
                        for x_v,y_v in zip(x,y):
                            test_y = x_v*m
                            vf = [y_v/float(y[-1]) - test_y/float(y[-1])]

                            if n2 in vf_values:
                                vf_data = vf_values[n2]
                                vf_data += vf
                                vf_values[n2] = vf_data
                            else:
                                vf_values[n2] = vf

                        x.append(max_dist)
                        y.append(y[-1])
                        ax.plot(x,y,label='%s'%(n2))


                data = OrderedDict(sorted(data.items()))
                
                ax.legend(loc=2,title='Legend',fancybox=True,fontsize=8)
                ax.set_xlim([0,max_dist+max_dist*0.01])
                ax.set_ylim([0,ylim])
                ax.set_title('Cumulative Frequency')
                ax.set_xlabel('Distance')
                ax.set_ylabel('Frequency')

                col_labels = data.keys()
                table_vals = [[],[],[],[],[],[],[],[],[],[],[],[]]
                
                for k,v in data.iteritems():
                    table_vals[0].append(len(v))
                    table_vals[1].append(round(np.mean(v),2))
                    table_vals[2].append(round(np.std(v),2))
                    table_vals[3].append(round(min(v),2))
                    table_vals[4].append(round(np.percentile(v, 25),2))
                    table_vals[5].append(round(np.percentile(v, 50),2))
                    table_vals[6].append(round(np.percentile(v, 75),2))                 
                    table_vals[7].append(round(max(v),2))
                    table_vals[8].append(round(np.std(v)/np.mean(v),2))
                
                for k,vf in vf_values.iteritems():
                    table_vals[9].append(round(max(vf),2))
                    table_vals[10].append(round(min(vf),2))
                    table_vals[11].append(round(math.fabs(max(vf))+ math.fabs(min(vf)),2))

                ax = fig.add_subplot(2,1,2)
                ax.axis('tight')
                ax.axis('off')
                
                row_labels = ['Count','mean','std','min','25%','50%','75%','Max','CoV',r'D$\^+$',r'D$\^-$','V$\mathit{f}$']
                col_len = len(col_labels)
                colW = [0.95/col_len]*col_len
                
                table = plt.table(colWidths = colW,cellText=table_vals,rowLabels=row_labels,colLabels=col_labels,loc='center',cellLoc='center')
   
                plt.show()
		
    except Exception,e:
        print e
        time.sleep(20)

if __name__ == "__main__":        
    ###Inputs###
        
    data = sys.argv[1]

    main(data)

