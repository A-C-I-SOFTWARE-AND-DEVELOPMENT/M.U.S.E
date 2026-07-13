// Engine-independent deterministic helpers shared by SynapseUniverse,
// SynapseCinematic, and tools/universe-selfcheck. This header deliberately
// uses only the C++17 standard library so the exact production math can be
// compiled without Unreal Engine.
#pragma once

#include <array>
#include <cmath>
#include <cstdint>
#include <iomanip>
#include <sstream>
#include <string>
#include <utility>
#include <vector>

namespace MuseUniverseMath
{
	inline constexpr double AtlasSphereDiameterMeters = 210.0;
	inline constexpr double AxialSpineLengthMeters = 1800.0;
	inline constexpr double CrownRingDiameterMeters = 1200.0;
	inline constexpr double NavigationClearanceMeters = 12.0;
	inline constexpr double DefaultRingDegreesPerSecond = 0.25;
	inline constexpr double DefaultInteraxialMillimeters = 65.0;

	struct Vector3d
	{
		double X = 0.0;
		double Y = 0.0;
		double Z = 0.0;
	};

	inline constexpr double MetersToCentimeters(const double Meters)
	{
		return Meters * 100.0;
	}

	inline constexpr std::pair<double, double> CounterRotationPair(const double DegreesPerSecond)
	{
		return {DegreesPerSecond, -DegreesPerSecond};
	}

	inline constexpr std::pair<double, double> StereoOffsetsMeters(const double InteraxialMillimeters)
	{
		const double HalfMeters = InteraxialMillimeters / 2000.0;
		return {-HalfMeters, HalfMeters};
	}

	inline std::pair<Vector3d, Vector3d> ConvergenceVectors(
		const double InteraxialMillimeters,
		const double ConvergenceDistanceMeters)
	{
		const double HalfMeters = InteraxialMillimeters / 2000.0;
		const double Distance = ConvergenceDistanceMeters > 1e-9 ? ConvergenceDistanceMeters : 1e-9;
		const double Length = std::sqrt(HalfMeters * HalfMeters + Distance * Distance);
		return {
			Vector3d{HalfMeters / Length, Distance / Length, 0.0},
			Vector3d{-HalfMeters / Length, Distance / Length, 0.0},
		};
	}

	inline constexpr Vector3d StationaryDockTransform(const double /*ElapsedSeconds*/)
	{
		return {};
	}

	namespace Detail
	{
		inline constexpr std::array<std::uint32_t, 64> Sha256Constants = {
			0x428a2f98U, 0x71374491U, 0xb5c0fbcfU, 0xe9b5dba5U,
			0x3956c25bU, 0x59f111f1U, 0x923f82a4U, 0xab1c5ed5U,
			0xd807aa98U, 0x12835b01U, 0x243185beU, 0x550c7dc3U,
			0x72be5d74U, 0x80deb1feU, 0x9bdc06a7U, 0xc19bf174U,
			0xe49b69c1U, 0xefbe4786U, 0x0fc19dc6U, 0x240ca1ccU,
			0x2de92c6fU, 0x4a7484aaU, 0x5cb0a9dcU, 0x76f988daU,
			0x983e5152U, 0xa831c66dU, 0xb00327c8U, 0xbf597fc7U,
			0xc6e00bf3U, 0xd5a79147U, 0x06ca6351U, 0x14292967U,
			0x27b70a85U, 0x2e1b2138U, 0x4d2c6dfcU, 0x53380d13U,
			0x650a7354U, 0x766a0abbU, 0x81c2c92eU, 0x92722c85U,
			0xa2bfe8a1U, 0xa81a664bU, 0xc24b8b70U, 0xc76c51a3U,
			0xd192e819U, 0xd6990624U, 0xf40e3585U, 0x106aa070U,
			0x19a4c116U, 0x1e376c08U, 0x2748774cU, 0x34b0bcb5U,
			0x391c0cb3U, 0x4ed8aa4aU, 0x5b9cca4fU, 0x682e6ff3U,
			0x748f82eeU, 0x78a5636fU, 0x84c87814U, 0x8cc70208U,
			0x90befffaU, 0xa4506cebU, 0xbef9a3f7U, 0xc67178f2U,
		};

		inline constexpr std::uint32_t RotateRight(const std::uint32_t Value, const std::uint32_t Bits)
		{
			return (Value >> Bits) | (Value << (32U - Bits));
		}
	}

	inline std::string Sha256Hex(const std::string& Input)
	{
		std::vector<std::uint8_t> Bytes(Input.begin(), Input.end());
		const std::uint64_t BitLength = static_cast<std::uint64_t>(Bytes.size()) * 8ULL;
		Bytes.push_back(0x80U);
		while ((Bytes.size() % 64U) != 56U)
		{
			Bytes.push_back(0U);
		}
		for (int Shift = 56; Shift >= 0; Shift -= 8)
		{
			Bytes.push_back(static_cast<std::uint8_t>((BitLength >> Shift) & 0xffULL));
		}

		std::array<std::uint32_t, 8> Hash = {
			0x6a09e667U, 0xbb67ae85U, 0x3c6ef372U, 0xa54ff53aU,
			0x510e527fU, 0x9b05688cU, 0x1f83d9abU, 0x5be0cd19U,
		};

		for (std::size_t Offset = 0; Offset < Bytes.size(); Offset += 64U)
		{
			std::array<std::uint32_t, 64> Words{};
			for (std::size_t Index = 0; Index < 16U; ++Index)
			{
				const std::size_t Base = Offset + Index * 4U;
				Words[Index] =
					(static_cast<std::uint32_t>(Bytes[Base]) << 24U) |
					(static_cast<std::uint32_t>(Bytes[Base + 1U]) << 16U) |
					(static_cast<std::uint32_t>(Bytes[Base + 2U]) << 8U) |
					static_cast<std::uint32_t>(Bytes[Base + 3U]);
			}
			for (std::size_t Index = 16U; Index < 64U; ++Index)
			{
				const std::uint32_t S0 = Detail::RotateRight(Words[Index - 15U], 7U) ^
					Detail::RotateRight(Words[Index - 15U], 18U) ^ (Words[Index - 15U] >> 3U);
				const std::uint32_t S1 = Detail::RotateRight(Words[Index - 2U], 17U) ^
					Detail::RotateRight(Words[Index - 2U], 19U) ^ (Words[Index - 2U] >> 10U);
				Words[Index] = Words[Index - 16U] + S0 + Words[Index - 7U] + S1;
			}

			std::uint32_t A = Hash[0];
			std::uint32_t B = Hash[1];
			std::uint32_t C = Hash[2];
			std::uint32_t D = Hash[3];
			std::uint32_t E = Hash[4];
			std::uint32_t F = Hash[5];
			std::uint32_t G = Hash[6];
			std::uint32_t H = Hash[7];

			for (std::size_t Index = 0; Index < 64U; ++Index)
			{
				const std::uint32_t Sum1 = Detail::RotateRight(E, 6U) ^
					Detail::RotateRight(E, 11U) ^ Detail::RotateRight(E, 25U);
				const std::uint32_t Choose = (E & F) ^ ((~E) & G);
				const std::uint32_t Temp1 = H + Sum1 + Choose +
					Detail::Sha256Constants[Index] + Words[Index];
				const std::uint32_t Sum0 = Detail::RotateRight(A, 2U) ^
					Detail::RotateRight(A, 13U) ^ Detail::RotateRight(A, 22U);
				const std::uint32_t Majority = (A & B) ^ (A & C) ^ (B & C);
				const std::uint32_t Temp2 = Sum0 + Majority;
				H = G;
				G = F;
				F = E;
				E = D + Temp1;
				D = C;
				C = B;
				B = A;
				A = Temp1 + Temp2;
			}

			Hash[0] += A;
			Hash[1] += B;
			Hash[2] += C;
			Hash[3] += D;
			Hash[4] += E;
			Hash[5] += F;
			Hash[6] += G;
			Hash[7] += H;
		}

		std::ostringstream Encoded;
		Encoded << std::hex << std::setfill('0');
		for (const std::uint32_t Word : Hash)
		{
			Encoded << std::setw(8) << Word;
		}
		return Encoded.str();
	}

	inline std::string StableVesselId(const std::string& RealmId, const std::string& AgentId)
	{
		std::string Material = RealmId;
		Material.push_back('\0');
		Material += AgentId;
		return "vsl_" + Sha256Hex(Material).substr(0, 20);
	}

	inline std::string DeterministicShotHash(const std::string& CanonicalShotRecord)
	{
		return Sha256Hex(CanonicalShotRecord);
	}
}

