using UnityEngine;

#if UNITY_EDITOR
using UnityEditor;
using System.Text.RegularExpressions;
#endif

namespace Sitekick
{
	public class ChipData : ScriptableObject
#if UNITY_EDITOR
		, ISerializationCallbackReceiver
#endif
	{
		public int id;

		#region Effect

		public enum EffectType
		{
			Default,
			Transformation,
			Background,
			Foreground
		}

		public enum EffectLayer
		{
			InFront = 0,
			Behind,
			Background,
			Foreground
		}

		[System.Flags]
		public enum EffectFlags
		{
			None = 0,
			HideBody = 1 << 0,
			HideEyes = 1 << 1,
			HideAntenna = 1 << 2,
			HideAll = HideBody | HideEyes | HideAntenna
		}

		public EffectType effectType = EffectType.Default;

		public EffectLayer effectLayer = EffectLayer.InFront;

		public EffectFlags effectFlags = EffectFlags.None;

		#endregion

#if UNITY_EDITOR

		public static bool TryParseChipName( string name, out int id )
		{
			Regex nameRegex = new Regex( @"Chip_0*([\d]+)" );
			var match = nameRegex.Match( name );
			if ( match != null && match.Groups.Count > 1 )
				return int.TryParse( match.Groups[1].Captures[0].ToString(), out id );

			id = -1;
			return false;
		}

		public void OnBeforeSerialize()
		{
			if ( TryParseChipName( this.name, out var newId ) && id != newId )
			{
				id = newId;
				EditorUtility.SetDirty( this );
			}
		}

		public void OnAfterDeserialize()
		{

		}

#endif
	}
}