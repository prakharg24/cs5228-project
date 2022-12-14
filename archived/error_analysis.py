import numpy as np
import matplotlib.pyplot as plt

def error_distribution(Ypred, Yval, outfile):
    error = (Ypred - Yval)**2
    hist_out = plt.hist(error, bins=20)
    for i in range(20):
        plt.text(hist_out[1][i],hist_out[0][i],str(hist_out[0][i]))
    plt.savefig(outfile)
    plt.clf()
    return

def error_outliers(Ypred, Yval, Xval, col_names):
    error = (Ypred - Yval)**2
    outlierX = Xval[error > 1e17]
    outlierYpred, outlierYval = Ypred[error > 1e17], Yval[error > 1e17]

    if len(outlierX) > 0:
        print(outlierYpred)
        print(outlierYval)
        # exit()
    return
