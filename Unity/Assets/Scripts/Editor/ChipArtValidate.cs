using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;
using Sitekick;

/// <summary>
/// Batch-mode verification of the generated chip art: every SVG must import as a
/// Sprite and every Chip_XXXX_Effect prefab must load with its art bound.
/// Run: Unity -batchmode -quit -executeMethod ChipArtValidate.Run
/// </summary>
public static class ChipArtValidate
{
	const string CHIPS = "Assets/Chips";
	const string REPORT = "Logs/chip-art-validation.txt";

	public static void Run()
	{
		var report = new StringBuilder();
		var problems = new List<string>();

		// ---- 1. SVG assets -------------------------------------------------
		var svgPaths = Directory.GetFiles( CHIPS, "*.svg", SearchOption.AllDirectories )
			.Select( p => p.Replace( '\\', '/' ) )
			.OrderBy( p => p )
			.ToArray();

		int spriteOk = 0;
		var noSprite = new List<string>();
		foreach ( var path in svgPaths )
		{
			var sprite = AssetDatabase.LoadAssetAtPath<Sprite>( path );
			if ( sprite == null )
				noSprite.Add( path );
			else
				spriteOk++;
		}

		report.AppendLine( $"SVG assets: {svgPaths.Length}  imported as Sprite: {spriteOk}  failed: {noSprite.Count}" );
		foreach ( var p in noSprite.Take( 40 ) )
			report.AppendLine( $"  NO SPRITE: {p}" );
		if ( noSprite.Count > 0 )
			problems.Add( $"{noSprite.Count} SVG assets did not import as Sprite" );

		// ---- 2. prefabs ----------------------------------------------------
		var prefabPaths = AssetDatabase.FindAssets( "t:Prefab", new[] { CHIPS } )
			.Select( AssetDatabase.GUIDToAssetPath )
			.Where( p => p.EndsWith( "_Effect.prefab" ) )
			.Where( p => System.Text.RegularExpressions.Regex.IsMatch( p, @"Chip_\d{4}_Effect\.prefab$" ) )
			.OrderBy( p => p )
			.ToArray();

		int withArt = 0, blank = 0, renderers = 0, emptySprites = 0;
		var badPrefabs = new List<string>();

		foreach ( var path in prefabPaths )
		{
			var prefab = AssetDatabase.LoadAssetAtPath<GameObject>( path );
			if ( prefab == null )
			{
				badPrefabs.Add( $"FAILED TO LOAD: {path}" );
				continue;
			}

			var reasons = new List<string>();
			var effect = prefab.GetComponent<ChipEffect>();
			var group = prefab.GetComponent<SortingGroup>();
			if ( effect == null ) reasons.Add( "missing ChipEffect" );
			if ( group == null ) reasons.Add( "missing SortingGroup" );

			var srs = prefab.GetComponentsInChildren<SpriteRenderer>( true );
			renderers += srs.Length;
			if ( srs.Length == 0 )
			{
				blank++;
			}
			else
			{
				withArt++;
				var missing = srs.Count( r => r.sprite == null );
				emptySprites += missing;
				if ( missing > 0 ) reasons.Add( $"{missing}/{srs.Length} renderers without sprite" );

				var bounds = new Bounds();
				bool first = true;
				foreach ( var r in srs.Where( r => r.sprite != null ) )
				{
					if ( first ) { bounds = r.bounds; first = false; }
					else bounds.Encapsulate( r.bounds );
				}

				if ( first )
				{
					reasons.Add( "no renderable sprites" );
				}
				else
				{
					var s = bounds.size;
					if ( !IsFinite( s.x ) || !IsFinite( s.y ) || s.x <= 0f || s.y <= 0f )
					{
						// the NaN can come from any one renderer (a sprite whose mesh
						// failed to build), so name the one that is actually broken
						var bad = srs.FirstOrDefault( r => r.sprite != null &&
							( !IsFinite( r.bounds.size.x ) || !IsFinite( r.bounds.size.y ) ) );
						if ( bad != null )
						{
							var bs = bad.sprite;
							reasons.Add( $"degenerate bounds {s} | renderer={bad.name} sprite={bs.name} " +
								$"verts={bs.vertices.Length} rect={bs.rect} " +
								$"tex={( bs.texture == null ? "null" : bs.texture.width + "x" + bs.texture.height )} " +
								$"localPos={bad.transform.localPosition} localScale={bad.transform.localScale}" );
						}
						else
						{
							var r0 = srs.First( r => r.sprite != null );
							var spr = r0.sprite;
							reasons.Add( $"degenerate bounds {s} | sprite={spr.name} rect={spr.rect} " +
								$"tex={( spr.texture == null ? "null" : spr.texture.width + "x" + spr.texture.height )} " +
								$"spriteBounds={spr.bounds} localPos={r0.transform.localPosition} localScale={r0.transform.localScale}" );
						}
					}
					else if ( s.x > 60f || s.y > 60f )
						reasons.Add( $"implausible bounds {s.x:F1}x{s.y:F1}" );
				}
			}

			if ( reasons.Count > 0 )
				badPrefabs.Add( $"{path}: {string.Join( "; ", reasons )}" );
		}

		report.AppendLine( $"Prefabs: {prefabPaths.Length}  with art: {withArt}  blank (no effect): {blank}" );
		report.AppendLine( $"SpriteRenderers: {renderers}  renderers without sprite: {emptySprites}" );
		report.AppendLine( $"Prefabs with problems: {badPrefabs.Count}" );
		foreach ( var b in badPrefabs.Take( 60 ) )
			report.AppendLine( $"  {b}" );
		if ( badPrefabs.Count > 0 )
			problems.Add( $"{badPrefabs.Count} prefabs have problems" );

		// ---- 3. ChipData ---------------------------------------------------
		var chipData = AssetDatabase.FindAssets( "t:ChipData", new[] { CHIPS } )
			.Select( AssetDatabase.GUIDToAssetPath )
			.Select( p => AssetDatabase.LoadAssetAtPath<ChipData>( p ) )
			.Where( c => c != null )
			.ToArray();
		int mismatched = chipData.Count( c =>
		{
			var m = System.Text.RegularExpressions.Regex.Match( c.name, @"Chip_(\d{4})$" );
			return !m.Success || int.Parse( m.Groups[1].Value ) != c.id;
		} );
		report.AppendLine( $"ChipData assets: {chipData.Length}  id/name mismatches: {mismatched}" );
		if ( mismatched > 0 )
			problems.Add( $"{mismatched} ChipData id/name mismatches" );

		// ---- 4. summary ----------------------------------------------------
		report.AppendLine();
		report.AppendLine( problems.Count == 0
			? "RESULT: OK - every SVG imported and every prefab is intact."
			: "RESULT: PROBLEMS\n  " + string.Join( "\n  ", problems ) );

		Directory.CreateDirectory( Path.GetDirectoryName( REPORT ) );
		File.WriteAllText( REPORT, report.ToString() );
		Debug.Log( "CHIPVALIDATE: report written to " + REPORT );
		Debug.Log( report.ToString() );
	}

	static bool IsFinite( float v )
	{
		return !float.IsNaN( v ) && !float.IsInfinity( v );
	}
}
