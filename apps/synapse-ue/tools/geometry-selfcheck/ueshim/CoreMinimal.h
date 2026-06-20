// MINIMAL NON-UE SHIM — NOT the real Unreal Engine headers.
//
// Just enough of CoreMinimal (FVector/FVector4/FVector2D/TArray/FMath and the
// reflection macros) to compile the *pure math* of MuseSacredGeometry.cpp with a
// plain C++17 compiler (clang/gcc), with no Unreal Engine installed. It lets CI
// and the authoring container prove the geometry algorithms compile and are
// numerically correct independent of the engine. The real engine types are used
// when the project is built with UE 5.6 on the owner's machine.
//
// This shim deliberately covers ONLY the surface MuseSacredGeometry.cpp uses.
#pragma once

#include <cmath>
#include <cstdint>
#include <utility>
#include <vector>

using int32 = std::int32_t;
using uint8 = std::uint8_t;

// Reflection macros collapse to nothing outside UHT.
#define UENUM(...)
#define UMETA(...)
#define SYNAPSECORE_API

struct FVector2D
{
	double X = 0.0;
	double Y = 0.0;
	FVector2D() = default;
	FVector2D(double InX, double InY) : X(InX), Y(InY) {}
};

struct FVector
{
	double X = 0.0;
	double Y = 0.0;
	double Z = 0.0;
	FVector() = default;
	FVector(double InX, double InY, double InZ) : X(InX), Y(InY), Z(InZ) {}
	double Length() const { return std::sqrt(X * X + Y * Y + Z * Z); }
	FVector& operator/=(double S)
	{
		X /= S;
		Y /= S;
		Z /= S;
		return *this;
	}
};

struct FVector4
{
	double X = 0.0;
	double Y = 0.0;
	double Z = 0.0;
	double W = 0.0;
	FVector4() = default;
	FVector4(double InX, double InY, double InZ, double InW) : X(InX), Y(InY), Z(InZ), W(InW) {}
};

template <typename T>
struct TArray
{
	std::vector<T> Items;
	void Add(const T& Value) { Items.push_back(Value); }
	void Reserve(int32 N)
	{
		if (N > 0)
		{
			Items.reserve(static_cast<std::size_t>(N));
		}
	}
	int32 Num() const { return static_cast<int32>(Items.size()); }
	bool IsValidIndex(int32 I) const { return I >= 0 && I < Num(); }
	T& operator[](int32 I) { return Items[static_cast<std::size_t>(I)]; }
	const T& operator[](int32 I) const { return Items[static_cast<std::size_t>(I)]; }
	T* begin() { return Items.data(); }
	T* end() { return Items.data() + Items.size(); }
	const T* begin() const { return Items.data(); }
	const T* end() const { return Items.data() + Items.size(); }
};

struct FMath
{
	static double Sqrt(double X) { return std::sqrt(X); }
	static double Cos(double X) { return std::cos(X); }
	static double Sin(double X) { return std::sin(X); }
	static double Abs(double X) { return std::fabs(X); }
	template <typename T>
	static T Max(T A, T B)
	{
		return A > B ? A : B;
	}
};

template <typename T>
T&& MoveTemp(T& X)
{
	return std::move(X);
}
