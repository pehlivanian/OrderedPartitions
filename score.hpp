#ifndef __SCORE_HPP__
#define __SCORE_HPP__

#include <vector>
#include <list>
#include <limits>
#include <algorithm>
#include <numeric>
#include <iostream>
#include <cmath>
#include <exception>


#define UNUSED(expr) do { (void)(expr); } while (0)

namespace Objectives {
  enum class objective_fn { Gaussian = 0, 
			    Poisson = 1, 
			    RationalScore = 2 };

  
  struct optimizationFlagException : public std::exception {
   const char* what() const throw () {
    return "Optimized version not implemented";
  };
 };


  class ParametricContext {
  protected:
    std::vector<float> a_;
    std::vector<float> b_;
    int n_;
    std::vector<std::vector<float>> a_sums_;
    std::vector<std::vector<float>> b_sums_;
    objective_fn parametric_dist_;
    bool risk_partitioning_objective_;
    bool use_rational_optimization_;

  public:
    ParametricContext(std::vector<float> a, 
		      std::vector<float> b, 
		      int n, 
		      objective_fn parametric_dist,
		      bool risk_partitioning_objective,
		      bool use_rational_optimization
		      ) :
      a_{a},
      b_{b},
      n_{n},
      parametric_dist_{parametric_dist},
      risk_partitioning_objective_{risk_partitioning_objective},
      use_rational_optimization_{use_rational_optimization}

    {}

    virtual ~ParametricContext() = default;

    virtual void compute_partial_sums() {};

    virtual float compute_score_multclust(int, int) = 0;
    virtual float compute_score_multclust_optimized(int, int) = 0;
    virtual float compute_score_riskpart(int, int) = 0;
    virtual float compute_score_riskpart_optimized(int, int) = 0;

    virtual float compute_ambient_score_multclust(float, float) = 0;
    virtual float compute_ambient_score_riskpart(float, float) = 0;

    float compute_score(int i, int j) {
      if (risk_partitioning_objective_) {
	if (use_rational_optimization_) {
	  return compute_score_riskpart_optimized(i, j);
	}
	else {
	  return compute_score_riskpart(i, j);
	}
      }
      else {
	if (use_rational_optimization_) {
	  return compute_score_multclust_optimized(i, j);
	}
	else {
	  return compute_score_multclust(i, j);
	}
      }
    }
    
    float compute_ambient_score(float a, float b) {
      if (risk_partitioning_objective_) {
	return compute_ambient_score_riskpart(a, b);
      }
      else {
	return compute_ambient_score_multclust(a, b);
      }
    }
  };
  
  class PoissonContext : public ParametricContext {

  public:
    PoissonContext(std::vector<float> a, 
		   std::vector<float> b, 
		   int n, 
		   objective_fn parametric_dist,
		   bool risk_partitioning_objective,
		   bool use_rational_optimization) : ParametricContext(a,
								       b,
								       n,
								       parametric_dist,
								       risk_partitioning_objective,
								       use_rational_optimization)
    { if (use_rational_optimization) {
	compute_partial_sums();
      }
    }
  
    float compute_score_multclust(int i, int j) override {    
      // CHECK
      float C = std::accumulate(a_.begin()+i, a_.begin()+j, 0.);
      float B = std::accumulate(b_.begin()+i, b_.begin()+j, 0.);
      if (C > B) {
	return C*std::log(C/B) + B - C;
      } else {
	return 0.;
      }
    }

    float compute_score_riskpart(int i, int j) override {
      // CHECK
      float C = std::accumulate(a_.begin()+i, a_.begin()+j, 0.);
      float B = std::accumulate(b_.begin()+i, b_.begin()+j, 0.);
      return C*std::log(C/B);
    }
    
    float compute_ambient_score_multclust(float a, float b) override {
      // CHECK
      return a*std::log(a/b) + b - a;
    }

    float compute_ambient_score_riskpart(float a, float b) override {
      // CHECK
      if (a > b) {
	return a*std::log(a/b) + b - a;
      } else {
	return 0.;
      }
    }  

    void compute_partial_sums() override {
      throw optimizationFlagException();
    }

    float compute_score_multclust_optimized(int i, int j) override {
      UNUSED(i);
      UNUSED(j);
      throw optimizationFlagException();
    }
    
    float compute_score_riskpart_optimized(int i, int j) override {
      UNUSED(i);
      UNUSED(j);
      throw optimizationFlagException();
    }

  };

  class GaussianContext : public ParametricContext {

  public:
    GaussianContext(std::vector<float> a, 
		    std::vector<float> b, 
		    int n, 
		    objective_fn parametric_dist,
		    bool risk_partitioning_objective,
		    bool use_rational_optimization) : ParametricContext(a,
									b,
									n,
									parametric_dist,
									risk_partitioning_objective,
									use_rational_optimization)
    { if (use_rational_optimization) {
	compute_partial_sums();
      }
    }
  
    float compute_score_multclust(int i, int j) override {
      // CHECK
      float C = std::accumulate(a_.begin()+i, a_.begin()+j, 0.);
      float B = std::accumulate(b_.begin()+i, b_.begin()+j, 0.);
      if (C > B) {
	float summand = std::pow(C, 2) / B;
	return .5*(summand - 1);
      } else {
	return 0.;
      }
    }
  
    float compute_score_riskpart(int i, int j) override {
      // CHECK
      float C = std::accumulate(a_.begin()+i, a_.begin()+j, 0.);
      float B = std::accumulate(b_.begin()+i, b_.begin()+j, 0.);
      return C*C/2./B;
    }

    float compute_ambient_score_multclust(float a, float b) override {
      // CHECK
      return a*a/2./b + b/2. - a;
    }

    float compute_ambient_score_riskpart(float a, float b) override {
      // CHECK
      if (a > b) {
	return a*a/2./b + b/2. - a;
      } else {
	return 0.;
      }
    }

    void compute_partial_sums() override {
      throw optimizationFlagException();
    }

    float compute_score_multclust_optimized(int i, int j) override {
      UNUSED(i);
      UNUSED(j);
      throw optimizationFlagException();
    }
    
    float compute_score_riskpart_optimized(int i, int j) override {
      UNUSED(i);
      UNUSED(j);
      throw optimizationFlagException();
    }

  };

  class RationalScoreContext : public ParametricContext {
    // This class doesn't correspond to any regular exponential family,
    // it is used to define ambient functions on the partition polytope
    // for targeted applications - quadratic approximations to loss, for
    // XGBoost, e.g.

  public:
    RationalScoreContext(std::vector<float> a,
			 std::vector<float> b,
			 int n,
			 objective_fn parametric_dist,
			 bool risk_partitioning_objective,
			 bool use_rational_optimization) : ParametricContext(a,
									     b,
									     n,
									     parametric_dist,
									     risk_partitioning_objective,
									     use_rational_optimization)
    { if (use_rational_optimization) {
	compute_partial_sums();
      }
    }

    void compute_partial_sums() override {
      float a_cum;
      a_sums_ = std::vector<std::vector<float>>(n_, std::vector<float>(n_+1, std::numeric_limits<float>::min()));
      b_sums_ = std::vector<std::vector<float>>(n_, std::vector<float>(n_+1, std::numeric_limits<float>::min()));
    
      for (int i=0; i<n_; ++i) {
	a_sums_[i][i] = 0.;
	b_sums_[i][i] = 0.;
      }

      for (int i=0; i<n_; ++i) {
	a_cum = -a_[i-1];
	for (int j=i+1; j<=n_; ++j) {
	  a_cum += a_[j-2];
	  a_sums_[i][j] = a_sums_[i][j-1] + (2*a_cum + a_[j-1])*a_[j-1];
	  b_sums_[i][j] = b_sums_[i][j-1] + b_[j-1];
	}
      }  
    }
  
    float compute_score_multclust_optimized(int i, int j) override {
      float score = a_sums_[i][j] / b_sums_[i][j];
      return score;
    }

    float compute_score_multclust(int i, int j) override {
      float score = std::pow(std::accumulate(a_.begin()+i, a_.begin()+j, 0.), 2) /
	std::accumulate(b_.begin()+i, b_.begin()+j, 0.);
      return score;
    }
  
    float compute_score_riskpart(int i, int j) override {
      return compute_score_multclust(i, j);
    }

    float compute_score_riskpart_optimized(int i, int j) override {
      return compute_score_multclust_optimized(i, j);
    }

    float compute_ambient_score_multclust(float a, float b) override {
      return a*a/b;
    }

    float compute_ambient_score_riskpart(float a, float b) override {
      return a*a/b;
    }

  };

} // namespace Objectives


#endif
