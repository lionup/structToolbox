''' Module that contains the likelihood calculations.
'''

# standard library
import scipy.stats
import numpy        as np

# project library
from _auxiliary import cdfConditional_single, cdfConditional_multiple

import tools.computation.f90.f90_main     as    fort

def sampleLikelihood(obsEconomy, parasObj, static, commObj):
    ''' Function calculates the sample likelihood.
    '''
    # Distribute class attributes.
    numAgents = obsEconomy.getAttr('numAgents')

    # Select implementation
    if(static): 
        
        likl = _speedyCalculation(obsEconomy, parasObj)
    
    else:
    
        # Calculate likelihood.        
        if(commObj is not None):
            
            likl = commObj.evaluate(parasObj)
            
        else:
        
            likl = _scalarEvaluations(obsEconomy, parasObj)

    # Scaling.
    likl = (1.0/float(numAgents))*likl

    # Quality checks
    assert (np.isfinite(likl))
    assert (isinstance(likl, float))    
    
    # Finishing.
    return likl

''' Private functions.
'''
def _speedyCalculation(obsEconomy, parasObj):
    ''' Calculation of sample likelihood.
    '''
    # Distribute class attributes
    attr      = obsEconomy.getAttr('attr')
    
    wages     = obsEconomy.getAttr('wages') 

    choices   = obsEconomy.getAttr('choices')
    
    numAgents = obsEconomy.getAttr('numAgents')

    # Experience 
    coeffs        = parasObj.getParameters('experience')
                    
    z             = attr['experience']

    idxExperience = np.dot(z, coeffs.T) 
        
    # Wage 
    coeffs, int_ = parasObj.getParameters('wage')
                    
    z            = attr['wage']

    idxWage      = np.dot(z, coeffs.T) + int_ + idxExperience
        
    # Utility 
    coeffs, int_ = parasObj.getParameters('utility')
                    
    z            = attr['utility']
                    
    idxUtility   = np.dot(z, coeffs.T) + int_
    
    # Children 
    coeff   = parasObj.getParameters('child')
                    
    cost    = parasObj.getParameters('cost')
                    
    subsidy = parasObj.getParameters('subsidy') 
                    
                    
    n            = attr['children']
                    
    idxChild     = np.dot(n, (cost - subsidy) + coeff.T)
        
    # Latent variable index
    xiStar = idxWage - idxChild - idxUtility
    
    # Home.
    xi   = parasObj.getParameters('xi')
                                            
    home = scipy.stats.norm.cdf(-xiStar, xi['mean'], xi['sd'])
        
    # Working.
    rho = parasObj.getParameters('rho')
                        
    eps  = parasObj.getParameters('eps')
                            
    eta  = parasObj.getParameters('eta')

                        
    # Working (unconditional)  
    real = wages - idxWage
    
    unconditional = scipy.stats.norm.pdf(real, eta['mean'], eta['sd'])      
    
    conditional = 1.0 - cdfConditional_multiple(-xiStar, xi, eta, real) 

    working     = conditional*unconditional
    
    working[np.isnan(working)] = 0.0
    
    # Aggregation.
    prob = choices*working + (1.0 - choices)*home
        
    prob = np.clip(prob, 1e-20, np.inf)
                        
    prob = -np.log(prob)
    
    likl = np.sum(prob)
    
    # Finishing
    return likl

def _scalarEvaluations(obsEconomy, parasObj):
    ''' Calculation of likelihood using OOP paradigm.
    '''
    # Distribute class attributes.
    numPeriods = obsEconomy.getAttr('numPeriods')
    
    agentObjs  = obsEconomy.getAttr('agentObjs')
        
    likl = 0.0
    
    # Calculate likelihood.
    for agentObj in agentObjs:
            
        # Update agent calculations.
        agentObj.unlock()
            
        agentObj.setAttr('parasObj', parasObj)
                
        agentObj.lock()
                
        # Collect probabilities.
        for period in range(numPeriods):
            
            # Calculate likelihood.
            prob = _individualLikelihood(agentObj, parasObj, period)
                                               
            # Collect results.
            likl = likl + prob

    # Finishing.
    return likl

def _individualLikelihood(agentObj, parasObj, period):
    ''' Calculation of individual likelihood.
    '''
    # Distribute agent attributes.
    wage     = agentObj.attr['wages'][period]

    position = agentObj.attr['states'][period + 1]
    
    idxWage  = agentObj.attr['w']['exAnte'][position]
    
    choice   = agentObj.attr['choices'][period]
    
    # Observable components.
    upper, lower = position[:-1] + '1', position[:-1] + '0'
    
    xiStar       = agentObj.attr['v']['exAnte'][upper] - \
                        agentObj.attr['v']['exAnte'][lower]
    
    xi   = parasObj.getParameters('xi')
    
    eta  = parasObj.getParameters('eta')
    
    # Select calculation.
    if(choice == 0):
                    
        prob = fort.wrapper_norm_cdf(-xiStar, xi['mean'], xi['sd'])
                
    else:
                                                            
        ''' Unconditional distribution.
        '''              
        real          = wage - idxWage
                                
        unconditional = fort.wrapper_norm_pdf(real, eta['mean'], eta['sd'])
                                   
        ''' Conditional distribution.
        '''
        conditional = 1.0 - cdfConditional_single(-xiStar, xi, eta, real) 
      
        prob        = conditional*unconditional
        
    # Aggregation.        
    prob = np.clip(prob, 1e-20, np.inf)
                        
    prob = -np.log(float(prob))
    
    # Quality checks.
    assert (np.isfinite(prob))
    assert (isinstance(prob, float))
    
    # Finishing.
    return prob

            