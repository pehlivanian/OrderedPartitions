#include "python_graph.hpp"
#include <thread>

std::vector<std::vector<int>> find_optimal_partition__PG(int n, 
			       int T, 
			       std::vector<float> a, 
			       std::vector<float> b) {
  
  auto pg = PartitionGraph(n, T, a, b);
  return pg.get_optimal_subsets_extern();
  
}

float find_optimal_weight__PG(int n,
			  int T,
			  std::vector<float> a,
			  std::vector<float> b) {
  auto pg = PartitionGraph(n, T, a, b);
  return pg.get_optimal_weight_extern();

}

std::pair<std::vector<std::vector<int>>, float> optimize_one__PG(int n,
								 int T,
								 std::vector<float> a,
								 std::vector<float> b) {
  
  auto pg = PartitionGraph(n, T, a, b);
  std::vector<std::vector<int>> subsets = pg.get_optimal_subsets_extern();
  float weight = pg.get_optimal_weight_extern();

  return std::make_pair(subsets, weight);
}

std::pair<std::vector<std::vector<int>>, float> sweep_best__PG(int n,
		  int T,
		  std::vector<float> a,
		  std::vector<float> b) {
  
  float best_weight = std::numeric_limits<float>::max(), weight;
  std::vector<std::vector<int>> subsets;
  
  for (int i=T; i>1; --i) {
    PartitionGraph pg{n, i, a, b};
    // XXX
    // Taking minimum here?
    weight = pg.get_optimal_weight_extern();
    std::cout << "NUM_PARTITIONS: " << T << " WEIGHT: " << weight << std::endl;
    if (weight < best_weight) {
      best_weight = weight;
      subsets = pg.get_optimal_subsets_extern();
    }
  }

  return std::make_pair(subsets, weight);
  
}

std::vector<std::pair<std::vector<std::vector<int>>, float>> sweep_parallel__PG(int n,
										int T,
										std::vector<float> a,
										std::vector<float> b) {
  ThreadsafeQueue<std::pair<std::vector<std::vector<int>>, float>> results_queue;
  
  auto task = [&results_queue](int n, int i, std::vector<float> a, std::vector<float> b){
    PartitionGraph pg{n, i, a, b};
    results_queue.push(std::make_pair(pg.get_optimal_subsets_extern(),
				      pg.get_optimal_weight_extern()));
  };

  std::vector<ThreadPool::TaskFuture<void>> v;
  
  for (int i=T; i>1; --i) {
    v.push_back(DefaultThreadPool::submitJob(task, n, i, a, b));
  }	       
  for (auto& item : v) 
    item.get();

  std::pair<std::vector<std::vector<int>>, float> result;
  std::vector<std::pair<std::vector<std::vector<int>>, float>> results;
  while (!results_queue.empty()) {
    bool valid = results_queue.waitPop(result);
    if (valid) {
      results.push_back(result);
    }
  }

  return results;

}

std::vector<std::pair<std::vector<std::vector<int>>, float>> sweep__PG(int n,
								       int T,
								       std::vector<float> a,
								       std::vector<float> b) {
  
  
  float weight;
  std::vector<std::vector<int>> subsets;
  std::vector<std::pair<std::vector<std::vector<int>>, float>> r;
  
  for (int i=T; i>1; --i) {
    PartitionGraph pg{n, i, a, b};
    weight = pg.get_optimal_weight_extern();
    subsets = pg.get_optimal_subsets_extern();

    r.push_back(std::make_pair(subsets, weight));
  }

  return r;
  
}
