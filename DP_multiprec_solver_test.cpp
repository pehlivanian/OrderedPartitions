#include "DP_multiprec_solver_test.hpp"

using namespace Objectives;

void print_subsets(std::vector<std::vector<int>>& subsets) {
  std::cout << "SUBSETS\n";
  std::cout << "[\n";
  std::for_each(subsets.begin(), subsets.end(), [](std::vector<int>& subset){
		  std::cout << "[";
		  std::copy(subset.begin(), subset.end(),
			    std::ostream_iterator<int>(std::cout, " "));
		  std::cout << "]\n";
		});
  std::cout << "]";
}

auto main() -> int {

  std::vector<cpp_dec_float_100> a10{0.0212651 , -0.20654906, -0.20654906, -0.20654906, -0.20654906,
      0.0212651 , -0.20654906,  0.0212651 , -0.20654906,  0.0212651};

  std::vector<cpp_dec_float_100> b10{0.22771114, 0.21809504, 0.21809504, 0.21809504, 0.21809504,
      0.22771114, 0.21809504, 0.22771114, 0.21809504, 0.22771114};

  std::vector<float> a10_flt32{0.0212651 , -0.20654906, -0.20654906, -0.20654906, -0.20654906,
      0.0212651 , -0.20654906,  0.0212651 , -0.20654906,  0.0212651};

  std::vector<float> b10_flt32{0.22771114, 0.21809504, 0.21809504, 0.21809504, 0.21809504,
      0.22771114, 0.21809504, 0.22771114, 0.21809504, 0.22771114};
  
  std::vector<cpp_dec_float_100> a{0.0212651 , -0.20654906, -0.20654906, -0.20654906, -0.20654906,
      0.0212651 , -0.20654906,  0.0212651 , -0.20654906,  0.0212651 ,
      -0.20654906,  0.0212651 , -0.20654906, -0.06581402,  0.0212651 ,
      0.03953075, -0.20654906,  0.16200014,  0.0212651 , -0.20654906,
      0.20296943, -0.18828341, -0.20654906, -0.20654906, -0.06581402,
      -0.20654906,  0.16200014,  0.03953075, -0.20654906, -0.20654906,
      0.03953075,  0.20296943, -0.20654906,  0.0212651 ,  0.20296943,
      -0.20654906,  0.0212651 ,  0.03953075, -0.20654906,  0.03953075};
  std::vector<cpp_dec_float_100> b{0.22771114, 0.21809504, 0.21809504, 0.21809504, 0.21809504,
      0.22771114, 0.21809504, 0.22771114, 0.21809504, 0.22771114,
      0.21809504, 0.22771114, 0.21809504, 0.22682739, 0.22771114,
      0.22745816, 0.21809504, 0.2218354 , 0.22771114, 0.21809504,
      0.218429  , 0.219738  , 0.21809504, 0.21809504, 0.22682739,
      0.21809504, 0.2218354 , 0.22745816, 0.21809504, 0.21809504,
      0.22745816, 0.218429  , 0.21809504, 0.22771114, 0.218429  ,
      0.21809504, 0.22771114, 0.22745816, 0.21809504, 0.22745816};

  std::vector<float> a_flt32{0.0212651 , -0.20654906, -0.20654906, -0.20654906, -0.20654906,
      0.0212651 , -0.20654906,  0.0212651 , -0.20654906,  0.0212651 ,
      -0.20654906,  0.0212651 , -0.20654906, -0.06581402,  0.0212651 ,
      0.03953075, -0.20654906,  0.16200014,  0.0212651 , -0.20654906,
      0.20296943, -0.18828341, -0.20654906, -0.20654906, -0.06581402,
      -0.20654906,  0.16200014,  0.03953075, -0.20654906, -0.20654906,
      0.03953075,  0.20296943, -0.20654906,  0.0212651 ,  0.20296943,
      -0.20654906,  0.0212651 ,  0.03953075, -0.20654906,  0.03953075};
  std::vector<float> b_flt32{0.22771114, 0.21809504, 0.21809504, 0.21809504, 0.21809504,
      0.22771114, 0.21809504, 0.22771114, 0.21809504, 0.22771114,
      0.21809504, 0.22771114, 0.21809504, 0.22682739, 0.22771114,
      0.22745816, 0.21809504, 0.2218354 , 0.22771114, 0.21809504,
      0.218429  , 0.219738  , 0.21809504, 0.21809504, 0.22682739,
      0.21809504, 0.2218354 , 0.22745816, 0.21809504, 0.21809504,
      0.22745816, 0.218429  , 0.21809504, 0.22771114, 0.218429  ,
      0.21809504, 0.22771114, 0.22745816, 0.21809504, 0.22745816};
    
  auto dp_multi = DPSolver_multi(10, 4, a10, b10);
  auto dp_multi_opt = dp_multi.get_optimal_subsets_extern();

  auto dp = DPSolver(10, 4, a10_flt32, b10_flt32, objective_fn::Gaussian, false, true);
  auto dp_opt = dp.get_optimal_subsets_extern();
  
  // auto pg = PartitionGraph(40, 5, a, b);
  // auto pg_opt = pg.get_optimal_subsets_extern();

  // std::cout << "Partition graph subsets:\n";
  // std::cout << "=======================\n";
  // print_subsets(pg_opt);
  std::cout << "\nDPSolver_multi subsets:\n";
  std::cout << "================\n";
  print_subsets(dp_multi_opt);
  // dp_multi.print_maxScore_();
  // dp_multi.print_nextStart_();
  std::cout << "DP_multi score: " << dp_multi.get_optimal_score_extern() << std::endl;
  
  std::cout << "\nDPSolver subsets:\n";
  std::cout << "================\n";
  print_subsets(dp_opt);
  // dp.print_maxScore_();
  // dp.print_nextStart_();
  std::cout << "DP score: " << dp.get_optimal_score_extern() << std::endl;

  /*
  std::vector<cpp_dec_float_100> a{1., 2., 3., 4., 5.};
  std::vector<cpp_dec_float_100> b{1., 1., 1., 1., 1.};
  auto dp = DPSolver(5, 3, a, b);
  */

  return 0;
}
