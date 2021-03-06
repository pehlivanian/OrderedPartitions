/* File : proto.i */
%module proto

%{
#include <boost/multiprecision/gmp.hpp>
#include <boost/multiprecision/cpp_dec_float.hpp>
#include "graph.hpp"
#include "python_graph.hpp"
#include "DP.hpp"
#include "python_dpsolver.hpp"
#include "LTSS.hpp"
#include "python_ltsssolver.hpp"
#include "DP_multiprec.hpp"
#include "python_dp_multisolver.hpp"
%}

%include "std_vector.i"
%include "std_pair.i"

namespace std {
%template(IArray) vector<int>;
%template(FArray) vector<float>;
%template(IArrayArray) vector<vector<int> >;
%template(IArrayFPair) pair<vector<int>, float>;
%template(IArrayArrayFPair) pair<vector<vector<int> >, float>;
%template(SWCont) vector<pair<vector<vector<int> >, float> >;
%template(GMPArray) vector<boost::multiprecision::cpp_dec_float_100>;
%template(SWGMPPair) pair<vector<vector<int> >, boost::multiprecision::cpp_dec_float_100>;
}

%include "python_graph.hpp"
%include "python_dpsolver.hpp"
%include "python_ltsssolver.hpp"
%include "python_dp_multisolver.hpp"

