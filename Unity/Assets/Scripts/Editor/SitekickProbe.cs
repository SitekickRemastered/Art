#if UNITY_EDITOR
using System.Collections.Generic;
using System.IO;
using System.Text;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace Sitekick
{
	/// <summary>
	/// Measures the Sitekick standing in the gallery scene, so the chip movies can
	/// be registered against the face the player actually sees. Writes
	/// Logs/sitekick-probe.txt.
	/// </summary>
	public static class SitekickProbe
	{
		const string ScenePath = "Assets/Scenes/ChipGallery.unity";
		const string ReportPath = "Logs/sitekick-probe.txt";

		[MenuItem( "Sitekick/Probe Gallery Sitekick" )]
		public static void Run()
		{
			EditorSceneManager.OpenScene( ScenePath, OpenSceneMode.Single );
			var gallery = Object.FindFirstObjectByType<ChipGallery>();
			var sitekick = gallery != null ? gallery.Sitekick : null;
			if ( sitekick == null )
			{
				File.WriteAllText( ReportPath, "no sitekick\n" );
				return;
			}

			var lines = new StringBuilder();
			lines.AppendLine( "sitekick root: " + sitekick.name + " pos " + sitekick.position.ToString( "0.0000" )
				+ " lossy scale " + sitekick.lossyScale.ToString( "0.0000" ) );

			foreach ( var t in sitekick.GetComponentsInChildren<Transform>( true ) )
			{
				var sr = t.GetComponent<SpriteRenderer>();
				if ( sr == null )
					continue;

				var b = sr.bounds;
				lines.AppendLine( string.Format(
					"{0,-14} order {1,3}  sprite {2,-22} world centre {3}  size {4}  localScale {5}  rect {6}",
					t.name, sr.sortingOrder, sr.sprite != null ? sr.sprite.name : "none",
					b.center.ToString( "0.0000" ), b.size.ToString( "0.0000" ),
					t.localScale.ToString( "0.0000" ),
					sr.sprite != null ? sr.sprite.rect.ToString() : "-" ) );
			}

			// the movie prefab of one rebuilt chip, for comparison
			foreach ( var chip in ChipMovieBuilder.Chips )
			{
				var path = "Assets/Chips/0001-0100/Chip_" + chip.ToString( "0000" ) + "/Chip_" + chip.ToString( "0000" ) + "_Effect.prefab";
				var prefab = AssetDatabase.LoadAssetAtPath<GameObject>( path );
				if ( prefab == null )
					continue;
				var instance = (GameObject) Object.Instantiate( prefab );
				foreach ( var sr in instance.GetComponentsInChildren<SpriteRenderer>( true ) )
				{
					lines.AppendLine( "chip " + chip + " movie sprite bounds " + sr.bounds.center.ToString( "0.0000" )
						+ " size " + sr.bounds.size.ToString( "0.0000" ) + " sort " + sr.sortingOrder );
					break;
				}
				Object.DestroyImmediate( instance );
				break;
			}

			File.WriteAllText( ReportPath, lines.ToString() );
			Debug.Log( lines.ToString() );
		}
	}
}
#endif
