#if UNITY_EDITOR
using Sitekick;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

public class EditorSitekick : MonoBehaviour
{
	[SerializeField]
	protected GameObject bodyObj, eyesObj, antennaObj;

	protected List<SpriteRenderer> sprites = null;

	protected ChipData.EffectFlags currentEffectFlags;

	public void SetEffectFlags( ChipData.EffectFlags effectFlags )
	{
		if ( currentEffectFlags == effectFlags )
			return;

		currentEffectFlags = effectFlags;

		if ( bodyObj != null )
			bodyObj.SetActive( ( effectFlags & ChipData.EffectFlags.HideBody ) != ChipData.EffectFlags.HideBody );

		if ( eyesObj != null )
			eyesObj.SetActive( ( effectFlags & ChipData.EffectFlags.HideEyes ) != ChipData.EffectFlags.HideEyes );

		if ( antennaObj != null )
			antennaObj.SetActive( ( effectFlags & ChipData.EffectFlags.HideAntenna ) != ChipData.EffectFlags.HideAntenna );
	}

	public void SetAlpha( float alpha )
	{
		if ( sprites == null )
			sprites = GetComponentsInChildren<SpriteRenderer>().ToList();

		foreach ( var sprite in sprites )
		{
			var color = sprite.color;
			color.a = alpha;
			sprite.color = color;
		}
	}
}
#endif