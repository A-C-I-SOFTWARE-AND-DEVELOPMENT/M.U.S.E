// MuseSacredGeometry implementation — see MuseSacredGeometry.h.
// Copyright A-C-I Software & Development. All rights reserved.
//
// Ported 1:1 from apps/synapse-ue/tools/sacred_geometry_reference.py (which is
// executed in the authoring container to prove the counts/constants this file
// must reproduce). Keep the two in lockstep.

#include "MuseSacredGeometry.h"

namespace
{
	// Double-precision pi (FVector components are doubles in UE5; the float PI
	// macro would lose golden-angle precision).
	constexpr double MusePi = 3.14159265358979323846;

	/** One index permutation of {0,1,2,3} with its parity. */
	struct FPerm4
	{
		int32 I[4];
		bool bEven;
	};

	/** All 24 permutations of {0,1,2,3}, each tagged even/odd by inversions. */
	TArray<FPerm4> AllPermutations()
	{
		TArray<FPerm4> Out;
		Out.Reserve(24);
		for (int32 A = 0; A < 4; ++A)
		{
			for (int32 B = 0; B < 4; ++B)
			{
				if (B == A)
				{
					continue;
				}
				for (int32 C = 0; C < 4; ++C)
				{
					if (C == A || C == B)
					{
						continue;
					}
					const int32 D = 6 - A - B - C;
					const int32 P[4] = {A, B, C, D};
					int32 Inversions = 0;
					for (int32 i = 0; i < 4; ++i)
					{
						for (int32 j = i + 1; j < 4; ++j)
						{
							if (P[i] > P[j])
							{
								++Inversions;
							}
						}
					}
					FPerm4 Perm;
					Perm.I[0] = A;
					Perm.I[1] = B;
					Perm.I[2] = C;
					Perm.I[3] = D;
					Perm.bEven = (Inversions % 2) == 0;
					Out.Add(Perm);
				}
			}
		}
		return Out;
	}

	/** Append every independent sign combination of Base (zero entries are not
	 *  flipped — that would only produce duplicates). */
	void AppendSigned(TArray<FVector4>& Out, const double Base[4])
	{
		int32 NonZero[4];
		int32 Count = 0;
		for (int32 k = 0; k < 4; ++k)
		{
			if (Base[k] != 0.0)
			{
				NonZero[Count++] = k;
			}
		}
		const int32 Combos = 1 << Count;
		for (int32 Mask = 0; Mask < Combos; ++Mask)
		{
			double V[4] = {Base[0], Base[1], Base[2], Base[3]};
			for (int32 Bit = 0; Bit < Count; ++Bit)
			{
				if (Mask & (1 << Bit))
				{
					V[NonZero[Bit]] = -V[NonZero[Bit]];
				}
			}
			Out.Add(FVector4(V[0], V[1], V[2], V[3]));
		}
	}

	/** Append all (or only even) coordinate permutations of Values, each with
	 *  every independent sign combination. */
	void AppendPermsSigned(TArray<FVector4>& Out, const double Values[4], bool bEvenOnly)
	{
		static const TArray<FPerm4> Perms = AllPermutations();
		for (const FPerm4& Perm : Perms)
		{
			if (bEvenOnly && !Perm.bEven)
			{
				continue;
			}
			const double Arranged[4] = {
				Values[Perm.I[0]], Values[Perm.I[1]], Values[Perm.I[2]], Values[Perm.I[3]]};
			AppendSigned(Out, Arranged);
		}
	}

	/** Remove exact duplicate vertices (after sign/permutation expansion). */
	void DedupeInPlace(TArray<FVector4>& Points)
	{
		TArray<FVector4> Unique;
		Unique.Reserve(Points.Num());
		for (const FVector4& P : Points)
		{
			bool bDup = false;
			for (const FVector4& Q : Unique)
			{
				if (FMath::Abs(P.X - Q.X) < 1e-6 && FMath::Abs(P.Y - Q.Y) < 1e-6 &&
					FMath::Abs(P.Z - Q.Z) < 1e-6 && FMath::Abs(P.W - Q.W) < 1e-6)
				{
					bDup = true;
					break;
				}
			}
			if (!bDup)
			{
				Unique.Add(P);
			}
		}
		Points = MoveTemp(Unique);
	}

	/** The three cyclic triples (0,a,b),(a,b,0),(b,0,a) — shared by the
	 *  icosahedron and dodecahedron generators. */
	void AppendCyclicTriples(TArray<FVector>& Out, double A, double B)
	{
		Out.Add(FVector(0.0, A, B));
		Out.Add(FVector(A, B, 0.0));
		Out.Add(FVector(B, 0.0, A));
	}
}  // namespace

namespace MuseGeometry
{
	double Phi()
	{
		return (1.0 + FMath::Sqrt(5.0)) / 2.0;
	}

	double GoldenAngleRadians()
	{
		return MusePi * (3.0 - FMath::Sqrt(5.0));
	}

	double GoldenAngleDegrees()
	{
		return GoldenAngleRadians() * 180.0 / MusePi;
	}

	TArray<FVector2D> VogelPhyllotaxis(int32 N)
	{
		TArray<FVector2D> Out;
		Out.Reserve(FMath::Max(0, N));
		const double Golden = GoldenAngleRadians();
		for (int32 i = 0; i < N; ++i)
		{
			const double R = FMath::Sqrt(static_cast<double>(i));
			const double Theta = static_cast<double>(i) * Golden;
			Out.Add(FVector2D(R * FMath::Cos(Theta), R * FMath::Sin(Theta)));
		}
		return Out;
	}

	TArray<FVector> FibonacciSphere(int32 N)
	{
		TArray<FVector> Out;
		Out.Reserve(FMath::Max(0, N));
		if (N <= 0)
		{
			return Out;
		}
		const double Golden = GoldenAngleRadians();
		for (int32 i = 0; i < N; ++i)
		{
			const double Z = 1.0 - 2.0 * (static_cast<double>(i) + 0.5) / static_cast<double>(N);
			const double Ring = FMath::Sqrt(FMath::Max(0.0, 1.0 - Z * Z));
			const double Theta = Golden * static_cast<double>(i);
			Out.Add(FVector(Ring * FMath::Cos(Theta), Z, Ring * FMath::Sin(Theta)));
		}
		return Out;
	}

	TArray<FVector> PlatonicVertices(EMusePlatonic Solid, bool bNormalize)
	{
		TArray<FVector> Out;
		const double P = Phi();
		switch (Solid)
		{
			case EMusePlatonic::Tetrahedron:
				Out.Add(FVector(1, 1, 1));
				Out.Add(FVector(1, -1, -1));
				Out.Add(FVector(-1, 1, -1));
				Out.Add(FVector(-1, -1, 1));
				break;
			case EMusePlatonic::Cube:
				for (double X : {-1.0, 1.0})
				{
					for (double Y : {-1.0, 1.0})
					{
						for (double Zc : {-1.0, 1.0})
						{
							Out.Add(FVector(X, Y, Zc));
						}
					}
				}
				break;
			case EMusePlatonic::Octahedron:
				Out.Add(FVector(1, 0, 0));
				Out.Add(FVector(-1, 0, 0));
				Out.Add(FVector(0, 1, 0));
				Out.Add(FVector(0, -1, 0));
				Out.Add(FVector(0, 0, 1));
				Out.Add(FVector(0, 0, -1));
				break;
			case EMusePlatonic::Icosahedron:
				for (double A : {-1.0, 1.0})
				{
					for (double B : {-P, P})
					{
						AppendCyclicTriples(Out, A, B);
					}
				}
				break;
			case EMusePlatonic::Dodecahedron:
				for (double X : {-1.0, 1.0})
				{
					for (double Y : {-1.0, 1.0})
					{
						for (double Zc : {-1.0, 1.0})
						{
							Out.Add(FVector(X, Y, Zc));
						}
					}
				}
				{
					const double Inv = 1.0 / P;
					for (double A : {-Inv, Inv})
					{
						for (double B : {-P, P})
						{
							AppendCyclicTriples(Out, A, B);
						}
					}
				}
				break;
		}

		if (bNormalize)
		{
			for (FVector& V : Out)
			{
				const double Len = V.Length();
				if (Len > 1e-9)
				{
					V /= Len;
				}
			}
		}
		return Out;
	}

	TArray<FVector4> PolytopeVertices(EMusePolytope Polytope)
	{
		TArray<FVector4> Out;
		const double P = Phi();
		const double Inv = 1.0 / P;
		const double Inv2 = 1.0 / (P * P);
		const double Root5 = FMath::Sqrt(5.0);

		switch (Polytope)
		{
			case EMusePolytope::Cell5:
			{
				// Centered R^4 embedding: regular-tetrahedron base + w-axis apex.
				const double S = 1.0 / FMath::Sqrt(10.0);
				Out.Add(FVector4(1.0, 1.0, 1.0, -S));
				Out.Add(FVector4(1.0, -1.0, -1.0, -S));
				Out.Add(FVector4(-1.0, 1.0, -1.0, -S));
				Out.Add(FVector4(-1.0, -1.0, 1.0, -S));
				Out.Add(FVector4(0.0, 0.0, 0.0, 4.0 * S));
				break;
			}
			case EMusePolytope::Cell16:
			{
				for (int32 Axis = 0; Axis < 4; ++Axis)
				{
					for (double Sign : {-1.0, 1.0})
					{
						double V[4] = {0.0, 0.0, 0.0, 0.0};
						V[Axis] = Sign;
						Out.Add(FVector4(V[0], V[1], V[2], V[3]));
					}
				}
				break;
			}
			case EMusePolytope::Tesseract:
			{
				for (double X : {-1.0, 1.0})
				{
					for (double Y : {-1.0, 1.0})
					{
						for (double Zc : {-1.0, 1.0})
						{
							for (double W : {-1.0, 1.0})
							{
								Out.Add(FVector4(X, Y, Zc, W));
							}
						}
					}
				}
				break;
			}
			case EMusePolytope::Cell24:
			{
				for (int32 Axis = 0; Axis < 4; ++Axis)
				{
					for (double Sign : {-1.0, 1.0})
					{
						double V[4] = {0.0, 0.0, 0.0, 0.0};
						V[Axis] = Sign;
						Out.Add(FVector4(V[0], V[1], V[2], V[3]));
					}
				}
				const double Half[4] = {0.5, 0.5, 0.5, 0.5};
				AppendSigned(Out, Half);
				DedupeInPlace(Out);
				break;
			}
			case EMusePolytope::Cell600:
			{
				// (a) 16 x (+-1/2)^4
				const double Half[4] = {0.5, 0.5, 0.5, 0.5};
				AppendSigned(Out, Half);
				// (b) 8 permutations of (+-1,0,0,0)
				for (int32 Axis = 0; Axis < 4; ++Axis)
				{
					for (double Sign : {-1.0, 1.0})
					{
						double V[4] = {0.0, 0.0, 0.0, 0.0};
						V[Axis] = Sign;
						Out.Add(FVector4(V[0], V[1], V[2], V[3]));
					}
				}
				// (c) 96 even permutations of 1/2 (+-phi,+-1,+-1/phi,0)
				const double Base[4] = {0.5 * P, 0.5, 0.5 * Inv, 0.0};
				AppendPermsSigned(Out, Base, /*bEvenOnly=*/true);
				DedupeInPlace(Out);
				break;
			}
			case EMusePolytope::Cell120:
			{
				const double F0[4] = {0.0, 0.0, 2.0, 2.0};
				AppendPermsSigned(Out, F0, /*bEvenOnly=*/false);  // 24
				const double F1[4] = {1.0, 1.0, 1.0, Root5};
				AppendPermsSigned(Out, F1, /*bEvenOnly=*/false);  // 64
				const double F2[4] = {Inv2, P, P, P};
				AppendPermsSigned(Out, F2, /*bEvenOnly=*/false);  // 64
				const double F3[4] = {Inv, Inv, Inv, P * P};
				AppendPermsSigned(Out, F3, /*bEvenOnly=*/false);  // 64
				const double F4[4] = {0.0, Inv2, 1.0, P * P};
				AppendPermsSigned(Out, F4, /*bEvenOnly=*/true);   // 96
				const double F5[4] = {0.0, Inv, P, Root5};
				AppendPermsSigned(Out, F5, /*bEvenOnly=*/true);   // 96
				const double F6[4] = {Inv, 1.0, P, 2.0};
				AppendPermsSigned(Out, F6, /*bEvenOnly=*/true);   // 192
				DedupeInPlace(Out);
				break;
			}
		}
		return Out;
	}

	FVector4 Rotate4D(const FVector4& P, EMuseRotationPlane Plane, double Angle)
	{
		int32 A = 0;
		int32 B = 1;
		switch (Plane)
		{
			case EMuseRotationPlane::XY: A = 0; B = 1; break;
			case EMuseRotationPlane::XZ: A = 0; B = 2; break;
			case EMuseRotationPlane::XW: A = 0; B = 3; break;
			case EMuseRotationPlane::YZ: A = 1; B = 2; break;
			case EMuseRotationPlane::YW: A = 1; B = 3; break;
			case EMuseRotationPlane::ZW: A = 2; B = 3; break;
		}
		const double Cos = FMath::Cos(Angle);
		const double Sin = FMath::Sin(Angle);
		double V[4] = {P.X, P.Y, P.Z, P.W};
		const double Va = V[A];
		const double Vb = V[B];
		V[A] = Va * Cos - Vb * Sin;
		V[B] = Va * Sin + Vb * Cos;
		return FVector4(V[0], V[1], V[2], V[3]);
	}

	FVector Project4DTo3D(const FVector4& P, EMuseProjection Mode, double Distance)
	{
		if (Mode == EMuseProjection::Stereographic)
		{
			const double Norm = FMath::Sqrt(P.X * P.X + P.Y * P.Y + P.Z * P.Z + P.W * P.W);
			const double N = (Norm > 1e-9) ? Norm : 1.0;
			const double X = P.X / N;
			const double Y = P.Y / N;
			const double Z = P.Z / N;
			const double W = P.W / N;
			const double Denom = 1.0 - W;
			const double S = (FMath::Abs(Denom) > 1e-9) ? (1.0 / Denom) : 1e9;
			return FVector(X * S, Y * S, Z * S);
		}

		// Perspective (Schlegel-style).
		const double Denom = Distance - P.W;
		const double S = (FMath::Abs(Denom) > 1e-9) ? (Distance / Denom) : 1e9;
		return FVector(P.X * S, P.Y * S, P.Z * S);
	}
}  // namespace MuseGeometry
